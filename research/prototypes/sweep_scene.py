import math, os, time
from manimlib import *
OUT = os.environ["SWEEP_OUT"]; N = int(os.environ.get("SWEEP_N", "60"))
class Sweep(Scene):
    def construct(self):
        axes = Axes((0, 10, 2), (0, 100, 25), width=8, height=4)
        axes.add_coordinate_labels(font_size=20)
        g = ValueTracker(1.0)
        curve = always_redraw(lambda: axes.get_graph(lambda i: 100/(1+math.exp(-g.get_value()*(i-5))), color=BLUE))
        lab = Tex(R"g = 0.00", font_size=36).to_corner(UR)
        num = lab.make_number_changeable("0.00")
        num.add_updater(lambda m: m.set_value(g.get_value()))
        self.add(axes, curve, lab)
        t0 = time.time()
        for k in range(N):
            g.set_value(0.2 + 3*k/(N-1))
            self.update_mobjects(0)
            self.update_frame(force_draw=True)
            self.get_image().save(os.path.join(OUT, f"f{k:03d}.png"))
        print(f"SWEEP {N} frames in {time.time()-t0:.2f}s", flush=True)
