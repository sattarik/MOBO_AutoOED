import numpy as np
from scipy.stats import norm
from algorithm.mobo.utils import safe_divide, expand
from .base import Acquisition


class EI(Acquisition):
    '''
    Expected Improvement
    '''
    requires_std = True

    def __init__(self, *args, **kwargs):
        self.y_min = None

    def fit(self, X, Y):
        self.y_min = np.min(Y, axis=0)

    def evaluate(self, val, calc_gradient=False, calc_hessian=False):
        y_mean, y_std = val['F'], val['S']
        z = safe_divide(self.y_min - y_mean, y_std)
        pdf_z = norm.pdf(z)
        cdf_z = norm.cdf(z)
        F = -(self.y_min - y_mean) * cdf_z - y_std * pdf_z

        dF, hF = None, None
        dy_mean, hy_mean, dy_std, hy_std = val['dF'], val['hF'], val['dS'], val['hS']

        if calc_gradient or calc_hessian:
            dz_y_mean = -safe_divide(1, y_std)
            dz_y_std = -safe_divide(self.y_min - y_mean, y_std ** 2)
            dpdf_z_z = -z * pdf_z

            dF_y_mean = cdf_z - (self.y_min - y_mean) * pdf_z * dz_y_mean - y_std * dpdf_z_z * dz_y_mean
            dF_y_std = (self.y_min - y_mean) * pdf_z * dz_y_std + pdf_z + y_std * dpdf_z_z * dz_y_std

            dF_y_mean, dF_y_std = expand(dF_y_mean), expand(dF_y_std)

        if calc_gradient:
            dF = dF_y_mean * dy_mean + dF_y_std * dy_std

        if calc_hessian:
            dpdf_z_y_mean = dpdf_z_z * dz_y_mean
            dpdf_z_y_std = dpdf_z_z * dz_y_std
            ddpdf_z_z_y_mean = -z * dpdf_z_y_mean - dz_y_mean * pdf_z
            ddpdf_z_z_y_std = -z * dpdf_z_y_std - dz_y_std * pdf_z
            ddz_y_std_y_std = safe_divide(self.y_min - y_mean, y_std ** 3)

            hF_y_mean = -pdf_z * dz_y_mean - \
                dz_y_mean * pdf_z + (self.y_min - y_mean) * dpdf_z_z * dz_y_mean ** 2 + \
                y_std * dz_y_mean * ddpdf_z_z_y_mean
            hF_y_std = (self.y_min - y_mean) * (dz_y_std * dpdf_z_y_std + pdf_z * ddz_y_std_y_std) + \
                dpdf_z_y_std + \
                dpdf_z_z * dz_y_std + y_std * dz_y_std * ddpdf_z_z_y_std + y_std * dpdf_z_z * ddz_y_std_y_std

            dy_mean, dy_std = expand(dy_mean), expand(dy_std)
            dy_mean_T, dy_std_T = dy_mean.transpose(0, 1, 3, 2), dy_std.transpose(0, 1, 3, 2)
            dF_y_mean, dF_y_std = expand(dF_y_mean), expand(dF_y_std)
            hF_y_mean, hF_y_std = expand(hF_y_mean, (-1, -2)), expand(hF_y_std, (-1, -2))

            hF = dF_y_mean * hy_mean + dF_y_std * hy_std + \
                hF_y_mean * dy_mean * dy_mean_T + hF_y_std * dy_std * dy_std_T

        return F, dF, hF