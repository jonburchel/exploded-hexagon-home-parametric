from PIL import Image
import colorsys
img = Image.open('renders/gap_review_atrium_eye56_material.png').convert('RGB')
w,h = img.size
rois = {
    'left_base': (int(0.08*w), int(0.55*h), int(0.35*w), int(0.90*h)),
    'right_base': (int(0.65*w), int(0.55*h), int(0.92*w), int(0.90*h)),
    'center_base': (int(0.40*w), int(0.55*h), int(0.60*w), int(0.90*h)),
}

def green_mask(rgb):
    r,g,b = [v/255.0 for v in rgb]
    h,s,v = colorsys.rgb_to_hsv(r,g,b)
    hue = h*360.0
    return (75 <= hue <= 165) and (s >= 0.18) and (0.08 <= v <= 0.95) and (g > r*1.05) and (g > b*1.05)

for name,(x0,y0,x1,y1) in rois.items():
    crop = img.crop((x0,y0,x1,y1))
    px = list(crop.getdata())
    n = len(px)
    g = sum(1 for p in px if green_mask(p))
    print(f'{name}: green_pixels={g} total={n} ratio={g/n:.6f}')
