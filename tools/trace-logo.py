# -*- coding: utf-8 -*-
"""로고 PNG -> SVG 벡터화 (개선판)
 개선점
  1) 잉크 레이어를 '색 거리'가 아니라 '휘도 차'로 계산 -> 회색 글자가 사라지지 않음
  2) 커버리지 맵을 3배 bilinear 업샘플 후 마칭스퀘어 -> 곡선이 매끄러움
  3) 꺾임 각도가 큰 지점은 직선으로 유지 -> 세리프·사각형 모서리가 살아남음
  4) 구멍(匠 흰 획)은 evenodd 로 처리
"""
import sys, math
sys.path.insert(0, __import__('os').path.dirname(__file__))
from _png import read_png

BG=(0xF5,0xF1,0xE8); RED=(0xD6,0x39,0x2C); INK=(0x1A,0x17,0x14)
def Y(c): return 0.299*c[0]+0.587*c[1]+0.114*c[2]
def cdist(a,b): return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))

def seal_bbox(px,w,h,tol=60):
    """확실한 인장색 픽셀의 '최대 연결 성분' 바운딩 박스를 찾는다.
    얇은 회색 글자의 서브픽셀 붉은 프린지도 인장색에 가깝게 나오므로,
    전역 박스를 쓰면 로고 전체가 인장으로 잡힌다. 연결 성분으로 실제 인장만 고른다."""
    mask=[[cdist(px[y][x],RED) < tol for x in range(w)] for y in range(h)]
    seen=[[False]*w for _ in range(h)]
    best=None; best_n=0
    for sy in range(h):
        for sx in range(w):
            if not mask[sy][sx] or seen[sy][sx]: continue
            stack=[(sx,sy)]; seen[sy][sx]=True
            xs=[]; ys=[]
            while stack:
                x,y=stack.pop(); xs.append(x); ys.append(y)
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx,ny=x+dx,y+dy
                    if 0<=nx<w and 0<=ny<h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx]=True; stack.append((nx,ny))
            if len(xs)>best_n:
                best_n=len(xs)
                best=(min(xs),min(ys),max(xs),max(ys))
    if not best: return None
    pad=3
    return (max(0,best[0]-pad), max(0,best[1]-pad),
            min(w-1,best[2]+pad), min(h-1,best[3]+pad), best_n)

def build_cov(px,w,h):
    """red: 인장 박스 안에서 색 거리 기준 / ink: 휘도 차 기준(회색 글자 보존)"""
    Dred = cdist(BG,RED)
    ybg, yink = Y(BG), Y(INK)
    box = seal_bbox(px,w,h)
    if box: print(f'  인장 박스: x {box[0]}-{box[2]}, y {box[1]}-{box[3]} (연결 픽셀 {box[4]}개)')
    red=[[0.0]*w for _ in range(h)]
    ink=[[0.0]*w for _ in range(h)]
    for y in range(h):
        in_box_y = box and box[1] <= y <= box[3]
        for x in range(w):
            p=px[y][x]
            if in_box_y and box[0] <= x <= box[2]:
                v = 1.0 - cdist(p,RED)/Dred
                red[y][x] = max(0.0, min(1.0, v))
                if red[y][x] > 0.45:
                    continue
            iv = (ybg - Y(p)) / (ybg - yink)
            ink[y][x] = max(0.0, min(1.0, iv))
    return red, ink, box

def upsample(cov,w,h,f):
    """bilinear 업샘플. 안티에일리어싱 정보를 서브픽셀 경계로 확장한다."""
    W,H = w*f, h*f
    out=[[0.0]*W for _ in range(H)]
    for Yy in range(H):
        sy=(Yy+0.5)/f-0.5
        y0=int(math.floor(sy)); ty=sy-y0
        y0c=max(0,min(h-1,y0)); y1c=max(0,min(h-1,y0+1))
        for Xx in range(W):
            sx=(Xx+0.5)/f-0.5
            x0=int(math.floor(sx)); tx=sx-x0
            x0c=max(0,min(w-1,x0)); x1c=max(0,min(w-1,x0+1))
            a=cov[y0c][x0c]; b=cov[y0c][x1c]; c=cov[y1c][x0c]; d=cov[y1c][x1c]
            out[Yy][Xx]=(a*(1-tx)+b*tx)*(1-ty)+(c*(1-tx)+d*tx)*ty
    return out,W,H

def marching(cov,w,h,t=0.5):
    def V(x,y):
        if x<0 or y<0 or x>=w or y>=h: return 0.0
        return cov[y][x]
    def ip(p1,p2,v1,v2):
        if abs(v2-v1)<1e-9: return p1
        a=(t-v1)/(v2-v1); return (p1[0]+(p2[0]-p1[0])*a, p1[1]+(p2[1]-p1[1])*a)
    segs=[]
    TAB={1:[(0,3)],2:[(1,0)],3:[(1,3)],4:[(2,1)],5:[(0,3),(2,1)],6:[(2,0)],7:[(2,3)],
         8:[(3,2)],9:[(0,2)],10:[(3,0),(1,2)],11:[(1,2)],12:[(3,1)],13:[(0,1)],14:[(3,0)]}
    for y in range(-1,h):
        for x in range(-1,w):
            v00=V(x,y); v10=V(x+1,y); v11=V(x+1,y+1); v01=V(x,y+1)
            idx=(1 if v00>=t else 0)|(2 if v10>=t else 0)|(4 if v11>=t else 0)|(8 if v01>=t else 0)
            if idx in (0,15): continue
            p00=(x+0.5,y+0.5); p10=(x+1.5,y+0.5); p11=(x+1.5,y+1.5); p01=(x+0.5,y+1.5)
            E=[ip(p00,p10,v00,v10), ip(p10,p11,v10,v11), ip(p01,p11,v01,v11), ip(p00,p01,v00,v01)]
            for a,b in TAB[idx]: segs.append((E[a],E[b]))
    return segs

def chain(segs):
    from collections import defaultdict
    K=lambda p:(round(p[0],3),round(p[1],3))
    nxt=defaultdict(list)
    for i,(a,b) in enumerate(segs): nxt[K(a)].append((K(b),b,i))
    used=[False]*len(segs); paths=[]
    for i,(a,b) in enumerate(segs):
        if used[i]: continue
        used[i]=True; start=K(a); path=[a,b]; cur=K(b)
        while cur!=start:
            cand=None
            for (kb,pb,j) in nxt.get(cur,()):
                if not used[j]: cand=(kb,pb,j); break
            if cand is None: break
            kb,pb,j=cand; used[j]=True; path.append(pb); cur=kb
        if cur==start and len(path)>=4: paths.append(path[:-1])
    return paths

def dp(pts,eps):
    if len(pts)<3: return pts
    def perp(p,a,b):
        dx=b[0]-a[0]; dy=b[1]-a[1]; n=math.hypot(dx,dy)
        if n==0: return math.hypot(p[0]-a[0],p[1]-a[1])
        return abs(dy*p[0]-dx*p[1]+b[0]*a[1]-b[1]*a[0])/n
    stack=[(0,len(pts)-1)]; keep=[False]*len(pts); keep[0]=keep[-1]=True
    while stack:
        s,e=stack.pop()
        dmax=0; idx=-1
        for i in range(s+1,e):
            d=perp(pts[i],pts[s],pts[e])
            if d>dmax: dmax=d; idx=i
        if idx>=0 and dmax>eps:
            keep[idx]=True; stack.append((s,idx)); stack.append((idx,e))
    return [p for p,k in zip(pts,keep) if k]

def to_path(pts, corner_deg=52):
    """꺾임이 corner_deg 이상이면 모서리를 직선으로 보존, 완만하면 2차 베지어."""
    n=len(pts)
    if n<3: return None
    def ang(i):
        a=pts[(i-1)%n]; b=pts[i]; c=pts[(i+1)%n]
        v1=(b[0]-a[0],b[1]-a[1]); v2=(c[0]-b[0],c[1]-b[1])
        n1=math.hypot(*v1); n2=math.hypot(*v2)
        if n1==0 or n2==0: return 0
        cs=max(-1,min(1,(v1[0]*v2[0]+v1[1]*v2[1])/(n1*n2)))
        return math.degrees(math.acos(cs))
    sharp=[ang(i)>=corner_deg for i in range(n)]
    mid=lambda a,b:((a[0]+b[0])/2,(a[1]+b[1])/2)
    d=[]; start = pts[0] if sharp[0] else mid(pts[0],pts[1])
    d.append(f"M{start[0]:.2f},{start[1]:.2f}")
    for i in range(n):
        c=pts[(i+1)%n]; nx=pts[(i+2)%n]
        if sharp[(i+1)%n]:
            d.append(f"L{c[0]:.2f},{c[1]:.2f}")
        else:
            m=mid(c,nx)
            d.append(f"Q{c[0]:.2f},{c[1]:.2f} {m[0]:.2f},{m[1]:.2f}")
    d.append("Z")
    return "".join(d)

def layer(cov,w,h,f,eps,min_area):
    up,W,H = upsample(cov,w,h,f)
    segs=marching(up,W,H)
    out=[]
    for p in chain(segs):
        s=dp(p,eps*f)
        if len(s)<3: continue
        a=0
        for i in range(len(s)):
            x1,y1=s[i]; x2,y2=s[(i+1)%len(s)]; a+=x1*y2-x2*y1
        if abs(a)/2 < min_area*f*f: continue
        # 원본 좌표계로 되돌린다
        s=[((x+0.5)/f-0.5, (y+0.5)/f-0.5) for x,y in s]
        d=to_path(s)
        if d: out.append(d)
    return out

def split_light_band(ink,px,w,h,box=None):
    """연한 회색 글자 줄을 찾아 별도 레이어로 분리한다.
    로고의 'shuriring clinic' 은 검정이 아니라 연회색이라 같은 임계값으로는 사라진다.
    행별 최대 커버리지가 중간대(0.25~0.7)인 연속 구간을 연한 글자 줄로 본다."""
    def in_seal(x,y):
        return box and box[0] <= x <= box[2] and box[1] <= y <= box[3]
    # 인장의 안티에일리어싱 가장자리도 중간 커버리지를 내므로 반드시 제외한다
    rowmax=[max((ink[y][x] for x in range(w) if not in_seal(x,y)), default=0.0) for y in range(h)]
    rows=[y for y in range(h) if 0.25 < rowmax[y] < 0.7]
    if not rows: return None, ink
    # 연속 구간 중 가장 긴 것
    groups=[]; cur=[rows[0]]
    for y in rows[1:]:
        if y==cur[-1]+1: cur.append(y)
        else: groups.append(cur); cur=[y]
    groups.append(cur)
    band=max(groups,key=len)
    if len(band) < 4: return None, ink
    y0,y1=band[0],band[-1]
    peak=max(rowmax[y0:y1+1])
    # 이 줄의 대표 색 = 커버리지가 가장 높은 픽셀들의 평균
    cand=[px[y][x] for y in range(y0,y1+1) for x in range(w)
          if ink[y][x] > peak*0.85 and not in_seal(x,y)]
    if cand:
        col=tuple(round(sum(c[i] for c in cand)/len(cand)) for i in range(3))
    else:
        col=(0x6F,0x6D,0x66)
    light=[[0.0]*w for _ in range(h)]
    ink2=[row[:] for row in ink]
    for y in range(y0,y1+1):
        for x in range(w):
            if in_seal(x,y): continue
            light[y][x] = max(0.0, min(1.0, ink[y][x]/peak))
            ink2[y][x] = 0.0
    print(f'  연한 글자 줄: y {y0}-{y1}, 최대 커버리지 {peak:.2f}, 색 #{col[0]:02X}{col[1]:02X}{col[2]:02X}')
    return (light, col), ink2

if __name__=='__main__':
    src,dst=sys.argv[1],sys.argv[2]
    w,h,px=read_png(src)
    red,ink,box=build_cov(px,w,h)
    lightinfo, ink = split_light_band(ink,px,w,h,box)
    F=3
    rp=layer(red,w,h,F,eps=0.22,min_area=0.8)
    ip_=layer(ink,w,h,F,eps=0.20,min_area=0.5)
    lp=[]; lcol='#6F6D66'
    if lightinfo:
        lcov,lcolt = lightinfo
        lcol='#%02X%02X%02X'%lcolt
        lp=layer(lcov,w,h,F,eps=0.16,min_area=0.25)
    print(f'  인장 path {len(rp)}개 / 글자 path {len(ip_)}개 / 연한글자 path {len(lp)}개')
    # evenodd 는 하나의 path 안에서만 적용된다. 레이어별로 모든 서브패스를 합쳐야
    # 안쪽 윤곽이 '구멍'이 된다(匠 의 흰 획, 의/원/璃 의 속공간).
    red_d = ''.join(rp); ink_d = ''.join(ip_); light_d = ''.join(lp)
    light_el = f'\n<path fill="{lcol}" fill-rule="evenodd" d="{light_d}"/>' if light_d else ''
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} 178" width="{w}" height="178" role="img" aria-label="슈리링의원">
<path fill="#D6392C" fill-rule="evenodd" d="{red_d}"/>
<path fill="#1A1714" fill-rule="evenodd" d="{ink_d}"/>{light_el}
</svg>'''
    open(dst,'w').write(svg)
    print(f'  {dst} — {len(svg)} bytes')
