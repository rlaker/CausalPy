import pymc as pm
import numpy as np
from sklearn.metrics import r2_score
import arviz as az


class ModelBuilder(pm.Model):
    """
    This is a wrapper around pm.Model to give scikit-learn like API
    """

    def __init__(self):
        super().__init__()
        self.idata = None

    def build_model(self, X, y, coords):
        raise NotImplementedError

    def _data_setter(self, X):
        with self.model:
            pm.set_data({"X": X})

    def fit(self, X, y, coords):
        self.build_model(X, y, coords)
        with self.model:
            self.idata = pm.sample()
            self.idata.extend(pm.sample_prior_predictive())
            self.idata.extend(pm.sample_posterior_predictive(self.idata))
        return self.idata

    def predict(self, X):
        self._data_setter(X)
        with self.model:  # sample with new input data
            post_pred = pm.sample_posterior_predictive(self.idata)
        return post_pred

    def score(self, X, y):
        yhat = self.predict(X)
        yhat = az.extract(yhat, group="posterior_predictive", var_names="y_hat").mean(
            dim="sample"
        )
        return r2_score(y, yhat)


class WeightedSumFitter(ModelBuilder):
    """Used for synthetic control experiments"""

    def build_model(self, X, y, coords):
        with self:
            self.add_coords(coords)
            n_predictors = X.shape[1]
            X = pm.MutableData("X", X, dims=["obs_ind", "coeffs"])
            y = pm.MutableData("y", y[:, 0], dims="obs_ind")
            beta = pm.Dirichlet("beta", a=np.ones(n_predictors))
            sigma = pm.HalfNormal("sigma", 1)
            mu = pm.Deterministic("mu", pm.math.dot(X, beta))
            pm.Normal("y_hat", mu, sigma, observed=y, dims="obs_ind")


class LinearRegression(ModelBuilder):
    def build_model(self, X, y, coords):
        with self:
            self.add_coords(coords)
            X = pm.MutableData("X", X, dims=["obs_ind", "coeffs"])
            y = pm.MutableData("y", y[:, 0], dims="obs_ind")
            beta = pm.Normal("beta", 0, 50, dims="coeffs")
            sigma = pm.HalfNormal("sigma", 1)
            mu = pm.Deterministic("mu", pm.math.dot(X, beta))
            pm.Normal("y_hat", mu, sigma, observed=y, dims="obs_ind")