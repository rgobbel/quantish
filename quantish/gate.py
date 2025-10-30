from quantish.qnumber import qify, Complex
import quantish.qnumber as qn
from quantish.angle import Angle
from quantish.particle import Particle
from quantish.util import Gensym

class Gate:

    def __init__(self, name, theta, states=(), alternative_measure=False):
        self.name = name
        self.id = Gensym(name)
        self.states = states
        if type(theta) is Angle:
            self.atheta = theta
            self.theta = theta.radians
        else:
            self.atheta = Angle(theta, unit='radians')
            self.theta = self.atheta.radians
        self.deg90 = qn.PI() / 2
        self.twist = self.theta - self.deg90

        self.mtheta = -self.theta
        self.mtwist = -self.twist

        self.cos_theta = self.theta.cos
        self.sin_theta = self.theta.sin
        self.cos2_theta = self.cos_theta**2
        self.cos_sin_theta = 1j * self.cos_theta * self.sin_theta
        self.mcos_sin_theta = -1j * self.cos_theta * self.sin_theta
        self.sin2_theta = self.sin_theta**2
        self.wplusf = self.cos_theta * (qn.I() * self.theta).exp
        self.wminusf = self.sin_theta * (qn.I() * self.twist).exp

        self.cos_twist = self.twist.cos
        self.sin_twist = self.twist.sin
        self.cos2_twist = self.cos_twist**2
        self.cos_sin_twist = 1j * self.cos_twist * self.sin_twist
        self.mcos_sin_twist = -1j * self.cos_twist * self.sin_twist
        self.sin2_twist = self.sin_twist**2
        self.wplusf_twist = self.cos_twist * (qn.I() * self.twist).exp
        self.wminusf_twist = self.sin_twist * (qn.I() * self.twist).exp

        self.cos_mtheta = self.mtheta.cos
        self.sin_mtheta = self.mtheta.sin
        self.cos2_mtheta = self.cos_mtheta ** 2
        self.cos_sin_mtheta = 1j * self.cos_mtheta * self.sin_mtheta
        self.mcos_sin_mtheta = -1j * self.cos_mtheta * self.sin_mtheta
        self.sin2_mtheta = self.sin_mtheta ** 2
        self.wplusfm = self.cos_mtheta * (qn.I() * self.mtheta).exp
        self.wminusfm = self.sin_mtheta * (qn.I() * self.twist).exp

        self.cos_mtwist = self.mtwist.cos
        self.sin_mtwist = self.mtwist.sin
        self.cos2_mtwist = self.cos_mtwist ** 2
        self.cos_sin_mtwist = 1j * self.cos_mtwist * self.sin_mtwist
        self.mcos_sin_mtwist = -1j * self.cos_mtwist * self.sin_mtwist
        self.sin2_mtwist = self.sin_mtwist ** 2
        self.wplusf_mtwist = self.cos_mtwist * (qn.I() * self.mtwist).exp
        self.wminusf_mtwist = self.sin_mtwist * (qn.I() * self.mtwist).exp

        self.alternative_measure = alternative_measure

    def __str__(self):
        return f'{self.name}({self.atheta.degrees:.1f}º)'

    def __repr__(self):
        return f'{self.name}({self.atheta.degrees:.2f}º)'

    def cpair3(self, w, plus=True, twist=False):
        """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
        w = qify(w)
        """basic weight rotation with trig scaling"""
        if plus and not twist:
            wplus = w * self.wplusf
            wminus = w * self.wminusf
        elif plus and twist:
            wplus = w * self.wplusf_twist
            wminus = w * self.wminusf_twist
        elif not plus and not twist:
            wplus = w * self.wplusfm
            wminus = w * self.wminusfm
        else:
            wplus = w * self.wplusf_mtwist
            wminus = w * self.wminusf_mtwist
        return wplus, wminus

    def cpair_alt(self, w, theta):
        # qw = qify(w)
        theta = qify(theta)
        """basic weight rotation with trig scaling"""
        twist = theta - self.deg90
        wplus = w * theta.cos * (qn.I() * theta).exp
        wminus = w * theta.sin * (qn.I() * twist).exp
        return wplus, wminus

    def cpair(self, w, theta):
        # qw = qify(w)
        theta = qify(theta)
        """from AIM-1026a, faster than doing the whole rotation"""
        # twist = theta - Gate.deg90
        c2a = w * theta.cos**2
        c2b = w * qn.I() * theta.cos * theta.sin
        c3a = w * theta.sin**2
        c3b = w * -qn.I() * theta.sin * theta.cos
        return c2a, c2b, c3a, c3b

    def cpair2(self, w, plus=True, twist=False):
        if plus and not twist:
            theta = self.theta
        elif plus and twist:
            theta = self.twist
        elif not plus and twist:
            theta = -self.twist
        else:
            theta = -self.theta
        """This is from AIM-1026a, and is much much faster than doing the whole rotation"""
        c2a = w * theta.cos ** 2
        c2b = w * 1j * theta.cos * theta.sin
        c3a = w * theta.sin ** 2
        c3b = w * -1j * theta.cos * theta.sin
        return c2a + c2b, c3a + c3b

    def cpair0(self, w, plus=True, twist=False):
        """This is from AIM-1026a"""
        if plus and not twist:
            c2a = w * self.cos2_theta
            c2b = w * self.cos_sin_theta
            c3a = w * self.sin2_theta
            c3b = w * self.mcos_sin_theta
        elif plus and twist:
            c2a = w * self.cos2_twist
            c2b = w * self.cos_sin_twist
            c3a = w * self.sin2_twist
            c3b = w * self.mcos_sin_twist
        elif not plus and not twist:
            c2a = w * self.cos2_mtheta
            c2b = w * self.cos_sin_mtheta
            c3a = w * self.sin2_mtheta
            c3b = w * self.mcos_sin_mtheta
        else:
            c2a = w * self.cos2_mtwist
            c2b = w * self.cos_sin_mtwist
            c3a = w * self.sin2_mtwist
            c3b = w * self.mcos_sin_mtwist
        return c2a + c2b, c3a + c3b

    def cpair1(self, w, plus=True, twist=False):
        """This follows the series of rotations described in AIM-1026a as well as Good and Real"""
        w = qify(w)
        if plus and not twist:
            theta = self.theta
        elif plus and twist:
            theta = self.twist
        elif not plus and twist:
            theta = -self.twist
        else:
            theta = -self.theta
        """basic weight rotation with trig scaling"""
        twist = self.twist
        wplus = w * theta.cos * (qn.I() * theta).exp
        wminus = w * theta.sin * (qn.I() * twist).exp
        return wplus, wminus

    def relative_angle(self, p:Particle):
        return  self.theta - p.v_0.phase

    def measure(self, p:Particle):
        """measure a particle through a gate, using floating point math

        weight -- complex-valued weight
        theta -- rotation angle
        sign -- plus or minus one
        """
        # following figure 4.4 in Good and Real
        c1 = p.weight
        if not self.alternative_measure:
            if p.sign > 0:  # straightforward rotation by theta
                par_a, par_b, perp_a, perp_b = self.cpair(c1, self.theta)
            else:
                par_a, par_b, perp_a, perp_b = self.cpair(c1, self.twist)
        else:
            if p.sign > 0:  # straightforward rotation by theta
                parallel, perpendicular = self.cpair3(c1, self.theta)
            else:
                parallel, perpendicular = self.cpair3(c1, self.twist)
            par_a, par_b = self.cpair3(parallel, -self.theta)
            perp_b, perp_a = self.cpair3(perpendicular, -self.theta)
        return [par_a, par_b, perp_a, perp_b]
