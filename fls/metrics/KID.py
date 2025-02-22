# From https://github.com/toshas/torch-fidelity/blob/master/torch_fidelity/metric_kid.py
import numpy as np
import torch
from fls.metrics.Metric import Metric
from tqdm import tqdm


KEY_METRIC_KID_MEAN = "kernel_inception_distance_mean"
KEY_METRIC_KID_STD = "kernel_inception_distance_std"


def mmd2(K_XX, K_XY, K_YY, unit_diagonal=False, mmd_est="unbiased"):
    m = K_XX.shape[0]
    assert K_XX.shape == (m, m)
    assert K_XY.shape == (m, m)
    assert K_YY.shape == (m, m)

    # Get the various sums of kernels that we'll use
    # Kts drop the diagonal, but we don't need to compute them explicitly
    if unit_diagonal:
        diag_X = diag_Y = 1
        sum_diag_X = sum_diag_Y = m
    else:
        diag_X = np.diagonal(K_XX)
        diag_Y = np.diagonal(K_YY)

        sum_diag_X = diag_X.sum()
        sum_diag_Y = diag_Y.sum()

    Kt_XX_sums = K_XX.sum(axis=1) - diag_X
    Kt_YY_sums = K_YY.sum(axis=1) - diag_Y
    K_XY_sums_0 = K_XY.sum(axis=0)

    Kt_XX_sum = Kt_XX_sums.sum()
    Kt_YY_sum = Kt_YY_sums.sum()
    K_XY_sum = K_XY_sums_0.sum()

    if mmd_est == "biased":
        mmd2 = (
            (Kt_XX_sum + sum_diag_X) / (m * m)
            + (Kt_YY_sum + sum_diag_Y) / (m * m)
            - 2 * K_XY_sum / (m * m)
        )
    else:
        mmd2 = (Kt_XX_sum + Kt_YY_sum) / (m * (m - 1))
        if mmd_est == "unbiased":
            mmd2 -= 2 * K_XY_sum / (m * m)
        else:
            mmd2 -= 2 * (K_XY_sum - np.trace(K_XY)) / (m * (m - 1))

    return mmd2


def polynomial_kernel(X, Y, degree=3, gamma=None, coef0=1):
    if gamma is None:
        gamma = 1.0 / X.shape[1]
    K = (np.matmul(X, Y.T) * gamma + coef0) ** degree
    return K


def polynomial_mmd(features_1, features_2, degree, gamma, coef0):
    k_11 = polynomial_kernel(
        features_1, features_1, degree=degree, gamma=gamma, coef0=coef0
    )
    k_22 = polynomial_kernel(
        features_2, features_2, degree=degree, gamma=gamma, coef0=coef0
    )
    k_12 = polynomial_kernel(
        features_1, features_2, degree=degree, gamma=gamma, coef0=coef0
    )
    return mmd2(k_11, k_12, k_22)


def kid_features_to_metric(features_1, features_2, **kwargs):
    assert torch.is_tensor(features_1) and features_1.dim() == 2
    assert torch.is_tensor(features_2) and features_2.dim() == 2
    assert features_1.shape[1] == features_2.shape[1]

    kid_subsets = 100
    kid_subset_size = min(1000, features_1.shape[0] // 2, features_2.shape[0] // 2)
    verbose = False

    n_samples_1, n_samples_2 = len(features_1), len(features_2)

    features_1 = features_1.cpu().numpy()
    features_2 = features_2.cpu().numpy()

    mmds = np.zeros(kid_subsets)
    rng = np.random.RandomState(42)

    for i in tqdm(
        range(kid_subsets),
        disable=not verbose,
        leave=False,
        unit="subsets",
        desc="Kernel Inception Distance",
    ):
        f1 = features_1[rng.choice(n_samples_1, kid_subset_size, replace=False)]
        f2 = features_2[rng.choice(n_samples_2, kid_subset_size, replace=False)]
        o = polynomial_mmd(
            f1,
            f2,
            3,
            None,
            1,
        )
        mmds[i] = o

    out = {
        KEY_METRIC_KID_MEAN: float(np.mean(mmds)),
        KEY_METRIC_KID_STD: float(np.std(mmds)),
    }

    return out


class KID(Metric):
    def __init__(self, mode="train", ref_size=50000):
        super().__init__()

        if self.mode == "train" and ref_size == 50000:
            self.name = "KID"
        else:
            self.name = f"{mode.title()} KID - {ref_size//1000}k"
        self.mode = mode
        self.ref_size = ref_size

    def compute_metric(
        self,
        train_feat,
        test_feat,
        gen_feat,
    ):
        def sample_ref_feat(feat):
            if feat.shape[0] > self.ref_size:
                return feat[
                    np.random.choice(feat.shape[0], self.ref_size, replace=False)
                ]
            return feat

        if self.mode == "train":
            ref_feat = sample_ref_feat(train_feat).cpu()
        elif self.mode == "test":
            ref_feat = sample_ref_feat(test_feat).cpu()
        else:
            raise ValueError("reference_feat must be one of 'train' or 'test'")

        vals = kid_features_to_metric(gen_feat.cpu(), ref_feat)
        return vals
