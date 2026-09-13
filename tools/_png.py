# -*- coding: utf-8 -*-
"""
PNG 로고를 SVG 로 벡터화한다.
외부 라이브러리 없이: PNG 디코드 -> 레이어별 커버리지 맵 -> 마칭스퀘어(선형보간)
-> 컨투어 체이닝 -> Douglas-Peucker 단순화 -> SVG path.
안티에일리어싱된 픽셀을 서브픽셀 경계 정보로 쓰기 때문에 계단이 크게 줄어든다.
"""
import sys, math, zlib, struct

# ---------- PNG 디코드 ----------
def read_png(path):
    data = open(path,'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n'
    pos=8; idat=b''; plte=None; w=h=bd=ct=None
    while pos < len(data):
        ln = struct.unpack('>I', data[pos:pos+4])[0]
        typ = data[pos+4:pos+8]; body = data[pos+8:pos+8+ln]
        if typ==b'IHDR': w,h,bd,ct,_,_,il = struct.unpack('>IIBBBBB', body); assert il==0
        elif typ==b'PLTE': plte=body
        elif typ==b'IDAT': idat+=body
        elif typ==b'IEND': break
        pos += 12+ln
    raw = zlib.decompress(idat)
    ch = {0:1,2:3,3:1,4:2,6:4}[ct]
    bpp = ch if bd==8 else (ch*2 if bd==16 else 1)
    stride = (w*ch*bd+7)//8
    out=bytearray(); prev=bytearray(stride); p=0
    for y in range(h):
        f=raw[p]; p+=1
        line=bytearray(raw[p:p+stride]); p+=stride
        if f==1:
            for i in range(bpp,stride): line[i]=(line[i]+line[i-bpp])&255
        elif f==2:
            for i in range(stride): line[i]=(line[i]+prev[i])&255
        elif f==3:
            for i in range(stride):
                a=line[i-bpp] if i>=bpp else 0
                line[i]=(line[i]+((a+prev[i])>>1))&255
        elif f==4:
            for i in range(stride):
                a=line[i-bpp] if i>=bpp else 0
                b=prev[i]; c=prev[i-bpp] if i>=bpp else 0
                pp=a+b-c; pa=abs(pp-a); pb=abs(pp-b); pc=abs(pp-c)
                pr=a if (pa<=pb and pa<=pc) else (b if pb<=pc else c)
                line[i]=(line[i]+pr)&255
        out+=line; prev=line
    px=[]
    for y in range(h):
        row=[]; base=y*stride
        for x in range(w):
            if ct==3:
                i=out[base+x]; row.append((plte[i*3],plte[i*3+1],plte[i*3+2]))
            elif ct==2:
                o=base+x*3; row.append((out[o],out[o+1],out[o+2]))
            elif ct==6:
                o=base+x*4; a=out[o+3]/255
                row.append(tuple(round(out[o+k]*a+255*(1-a)) for k in range(3)))
            else:
                g=out[base+x]; row.append((g,g,g))
        px.append(row)
    return w,h,px

# ---------- 커버리지 맵 ----------
def dist(a,b): return math.sqrt(sum((a[i]-b[i])**2 for i in range(3)))

def coverage(px,w,h,target,bg,exclude=None):
    """target 색에 가까울수록 1, bg 에 가까울수록 0. exclude 맵이 주면 그 영역은 0."""
    D = dist(bg,target)
    if D == 0: D = 1
    cov=[[0.0]*w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if exclude and exclude[y][x] > 0.5:
                continue
            d = dist(px[y][x], target)
            v = 1.0 - d/D
            cov[y][x] = 0.0 if v<0 else (1.0 if v>1 else v)
    return cov

# ---------- 마칭스퀘어 ----------
def interp(p1,p2,v1,v2,t):
    if abs(v2-v1) < 1e-9: return p1
    a=(t-v1)/(v2-v1)
    return (p1[0]+(p2[0]-p1[0])*a, p1[1]+(p2[1]-p1[1])*a)

def marching(cov,w,h,t=0.5):
    """픽셀 중심을 격자점으로 보고 등고선 세그먼트를 만든다."""
    def V(x,y):
        if x<0 or y<0 or x>=w or y>=h: return 0.0
        return cov[y][x]
    segs=[]
    for y in range(-1,h):
        for x in range(-1,w):
            # 셀 네 꼭짓점 (픽셀 중심 좌표)
            p00=(x+0.5,y+0.5);   v00=V(x,y)
            p10=(x+1.5,y+0.5);   v10=V(x+1,y)
            p11=(x+1.5,y+1.5);   v11=V(x+1,y+1)
            p01=(x+0.5,y+1.5);   v01=V(x,y+1)
            idx = (1 if v00>=t else 0)|(2 if v10>=t else 0)|(4 if v11>=t else 0)|(8 if v01>=t else 0)
            if idx==0 or idx==15: continue
            T=interp(p00,p10,v00,v10,t); R=interp(p10,p11,v10,v11,t)
            B=interp(p01,p11,v01,v11,t); L=interp(p00,p01,v00,v01,t)
            table={1:[(T,L)],2:[(R,T)],3:[(R,L)],4:[(B,R)],
                   5:[(T,L),(B,R)],6:[(B,T)],7:[(B,L)],8:[(L,B)],
                   9:[(T,B)],10:[(L,T),(R,B)],11:[(R,B)],12:[(L,R)],
                   13:[(T,R)],14:[(L,T)]}
            for s in table[idx]: segs.append(s)
    return segs

def chain(segs):
    """세그먼트를 닫힌 경로로 연결. 딕셔너리 인접맵으로 O(n)."""
    from collections import defaultdict
    K = lambda p: (round(p[0], 4), round(p[1], 4))
    nxt = defaultdict(list)          # 시작점 -> [(끝점키, 끝점좌표, 세그먼트인덱스)]
    for i, (a, b) in enumerate(segs):
        nxt[K(a)].append((K(b), b, i))
    used = [False] * len(segs)
    paths = []
    for i, (a, b) in enumerate(segs):
        if used[i]:
            continue
        used[i] = True
        start = K(a)
        path = [a, b]
        cur = K(b)
        while cur != start:
            cand = None
            for (kb, pb, j) in nxt.get(cur, ()):
                if not used[j]:
                    cand = (kb, pb, j)
                    break
            if cand is None:
                break
            kb, pb, j = cand
            used[j] = True
            path.append(pb)
            cur = kb
        if len(path) >= 4 and cur == start:
            paths.append(path[:-1])   # 닫힌 경로: 마지막 중복점 제거
    return paths

# ---------- 단순화 ----------
def dp(points, eps):
    if len(points)<3: return points
    def perp(p,a,b):
        dx=b[0]-a[0]; dy=b[1]-a[1]
        n=math.hypot(dx,dy)
        if n==0: return math.hypot(p[0]-a[0],p[1]-a[1])
        return abs(dy*p[0]-dx*p[1]+b[0]*a[1]-b[1]*a[0])/n
    dmax=0; idx=0
    for i in range(1,len(points)-1):
        d=perp(points[i],points[0],points[-1])
        if d>dmax: dmax=d; idx=i
    if dmax>eps:
        left=dp(points[:idx+1],eps); right=dp(points[idx:],eps)
        return left[:-1]+right
    return [points[0],points[-1]]

def smooth_path(pts):
    """꼭짓점 사이를 2차 베지어로 이어 계단을 부드럽게 한다."""
    if len(pts)<3: return None
    mid=lambda a,b:((a[0]+b[0])/2,(a[1]+b[1])/2)
    d=[]
    m0=mid(pts[0],pts[1])
    d.append(f"M{m0[0]:.2f},{m0[1]:.2f}")
    n=len(pts)
    for i in range(1,n):
        c=pts[i]; nxt=pts[(i+1)%n]; m=mid(c,nxt)
        d.append(f"Q{c[0]:.2f},{c[1]:.2f} {m[0]:.2f},{m[1]:.2f}")
    c=pts[0]; nxt=pts[1]; m=mid(c,nxt)
    d.append(f"Q{c[0]:.2f},{c[1]:.2f} {m[0]:.2f},{m[1]:.2f}")
    d.append("Z")
    return "".join(d)

def layer_to_paths(cov,w,h,eps=0.42,min_area=1.2):
    segs=marching(cov,w,h)
    paths=chain(segs)
    out=[]
    for p in paths:
        s=dp(p,eps)
        if len(s)<3: continue
        a=0
        for i in range(len(s)):
            x1,y1=s[i]; x2,y2=s[(i+1)%len(s)]
            a+=x1*y2-x2*y1
        if abs(a)/2 < min_area: continue
        d=smooth_path(s)
        if d: out.append(d)
    return out

if __name__=='__main__':
    src=sys.argv[1]; dst=sys.argv[2]
    w,h,px=read_png(src)
    BG=(0xF5,0xF1,0xE8); RED=(0xD6,0x39,0x2C); INK=(0x1A,0x17,0x14)
    red_cov=coverage(px,w,h,RED,BG)
    ink_cov=coverage(px,w,h,INK,BG,exclude=red_cov)
    print(f'  원본 {w}x{h}')
    red_paths=layer_to_paths(red_cov,w,h)
    ink_paths=layer_to_paths(ink_cov,w,h)
    print(f'  인장 레이어 path {len(red_paths)}개 / 글자 레이어 path {len(ink_paths)}개')
    open(dst+'.red','w').write('\n'.join(red_paths))
    open(dst+'.ink','w').write('\n'.join(ink_paths))
    print(f'  중간 결과 저장: {dst}.red / {dst}.ink')
