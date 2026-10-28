import math, os
from manimlib import *
OUT = os.environ["SVG_OUT"]
def hexa(rgb): return "#%02x%02x%02x" % tuple(int(255*max(0,min(1,c))) for c in rgb[:3])
def vmob_to_svg(scene, fw=FRAME_WIDTH, fh=FRAME_HEIGHT):
    parts = []
    for m in scene.get_mobject_family_members():
        if not isinstance(m, VMobject) or not m.has_points(): continue
        d = []
        for sp in m.get_subpaths():
            if len(sp) < 3: continue
            P = [(p[0], -p[1]) for p in sp]
            d.append("M%.3f %.3f" % P[0])
            for i in range(1, len(P) - 1, 2):
                d.append("Q%.3f %.3f %.3f %.3f" % (*P[i], *P[i+1]))
        if not d: continue
        fill = list(color_to_rgb(m.get_fill_color())) + [m.get_fill_opacity()]; stroke = list(color_to_rgb(m.get_stroke_color())) + [m.get_stroke_opacity()]
        sw = m.get_stroke_width()
        sw = float(sw[0]) if hasattr(sw, "__len__") else float(sw)
        parts.append('<path d="%s" fill="%s" fill-opacity="%.2f" stroke="%s" stroke-opacity="%.2f" stroke-width="%.4f" fill-rule="nonzero"/>' % (
            " ".join(d), hexa(fill), fill[3], hexa(stroke), stroke[3], sw * 0.01))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%.3f %.3f %.3f %.3f" style="background:#000">' % (-fw/2, -fh/2, fw, fh)
            + "".join(parts) + "</svg>")
class SvgTest(Scene):
    def construct(self):
        axes = Axes((0, 10, 2), (0, 100, 25), width=8, height=4)
        axes.add_coordinate_labels(font_size=20)
        curve = axes.get_graph(lambda i: 100/(1+math.exp(-1.2*(i-5))), color=BLUE)
        eq = Tex(R"r(I) = \frac{r_{\max}}{1 + e^{-g\,(I - I_{1/2})}}", font_size=40).to_edge(UP)
        self.add(axes, curve, eq)
        open(os.path.join(OUT, "frame.svg"), "w").write(vmob_to_svg(self))
        self.update_frame(force_draw=True); self.get_image().save(os.path.join(OUT, "frame.png"))
