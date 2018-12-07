# -*- coding: utf-8 -*-
"""Local Correlation Integral (LOCI).
Part of the codes are adapted from https://github.com/Cloudy10/loci
"""
# Author: Winston Li <jk_zhengli@hotmail.com>
# License: BSD 2 clause

from __future__ import division
from __future__ import print_function

import numpy as np
from sklearn.utils import check_array
from sklearn.utils.validation import check_is_fitted
from scipy.spatial.distance import pdist, squareform

from .base import BaseDetector


class LOCI(BaseDetector):
    """Local Correlation Integral.
    
    LOCI is highly effective for detecting outliers and groups of 
    outliers ( a.k.a.micro-clusters), which offers the following advantages 
    and novelties: (a) It provides an automatic, data-dictated cut-off to 
    determine whether a point is an outlier—in contrast, previous methods 
    force users to pick cut-offs, without any hints as to what cut-off value 
    is best for a given dataset. (b) It can provide a LOCI plot for each 
    point; this plot summarizes a wealth of information about the data in 
    the vicinity of the point, determining clusters, micro-clusters, their 
    diameters and their inter-cluster distances. None of the existing 
    outlier-detection methods can match this feature, because they output 
    only a single number for each point: its outlierness score.(c) It can 
    be computed as quickly as the best previous methods
    Read more in the :cite:`papadimitriou2003loci`.
    
    Parameters
    ----------
    contamination : float in (0., 0.5), optional (default=0.1) 
        The amount of contamination of the data set, i.e.
        the proportion of outliers in the data set. Used when fitting to
        define the threshold on the decision function.
    
    alpha : int, default = 0.5
        The neighbourhood parameter measures how large of a neighbourhood
        should be considered "local".
    
    k: int, default = 3
        An outlier cutoff threshold for determine whether or not a point 
        should be considered an outlier.

    Examples
    --------
    >>> from pyod.models.loci import LOCI
    >>> from pyod.utils.data import generate_data
    >>> n_train = 50
    >>> n_test = 50
    >>> contamination = 0.1
    >>> X_train, y_train, X_test, y_test = generate_data(
    >>>     n_train=n_train, n_test=n_test,
    >>>     contamination=contamination, random_state=42)
    >>>
    >>> clf = LOCI()
    >>> clf.fit(X_train)
    >>> print(clf.decision_scores_)
    """

    def __init__(self, contamination=0.1, alpha=0.5, k=3):
        super(LOCI, self).__init__(contamination=contamination)
        self._alpha = alpha
        self.threshold_ = k

    def _get_critical_values(self, dist_matrix, p_ix, r_max, r_min=0):
        """Computes the critical values of a given distance matrix.
        
        Parameters
        ----------
        dist_matrix : array-like, shape (n_samples, n_features)
            The distance matrix w.r.t. to the training samples.
        
        p_ix : int
            Subsetting index
        
        r_max : int
            Maximum neighbourhood radius
        
        r_min : int, default = 0
            Minimum neighbourhood radius
            
        Returns
        -------
        cv : array, shape (n_critical_val, )
            Returns a list of critical values.       
        """

        distances = dist_matrix[p_ix, :]
        mask = (r_min < distances) & (distances <= r_max)
        cv = np.sort(
            np.concatenate((distances[mask], distances[mask] / self._alpha)))
        return cv

    def _get_sampling_N(self, dist_matrix, p_ix, r):
        """Computes the set of r-neighbours.
        
        Parameters
        ----------
        dist_matrix : array-like, shape (n_samples, n_features)
            The distance matrix w.r.t. to the training samples.
        
        p_ix : int
            Subsetting index
        
        r : int
            Neighbourhood radius
        
            
        Returns
        -------
        sample : array, shape (n_sample, )
            Returns a list of neighbourhood data points.       
        """

        p_distances = dist_matrix[p_ix, :]
        sample = np.nonzero(p_distances <= r)[0]
        return sample

    def _get_alpha_n(self, dist_matrix, indices, r):
        """Computes the alpha neighbourhood points.
        
        Parameters
        ----------
        dist_matrix : array-like, shape (n_samples, n_features)
            The distance matrix w.r.t. to the training samples.
        
        indices : int
            Subsetting index
        
        r : int
            Neighbourhood radius
            
        Returns
        -------
        alpha_n : array, shape (n_alpha, )
            Returns the alpha neighbourhood points.       
        """

        if type(indices) is int:
            alpha_n = np.count_nonzero(
                dist_matrix[indices, :] < (r * self._alpha))
            return alpha_n
        else:
            alpha_n = np.count_nonzero(
                dist_matrix[indices, :] < (r * self._alpha), axis=1)
            return alpha_n

    def _calculate_decision_score(self, X):
        """Computes the outlier scores.
        
        Parameters
        ----------
        X : array-like, shape (n_samples, n_features)
            The input data points.
            
        Returns
        -------
        outlier_scores : list
            Returns the list of outlier scores for input dataset.       
        """
        outlier_scores = [0] * X.shape[0]
        dist_matrix = squareform(pdist(X, metric="euclidean"))
        max_dist = dist_matrix.max()
        r_max = max_dist / self._alpha

        for p_ix in range(X.shape[0]):
            critical_values = self._get_critical_values(dist_matrix, p_ix,
                                                        r_max)
            for r in critical_values:
                n_values = self._get_alpha_n(dist_matrix,
                                             self._get_sampling_N(dist_matrix,
                                                                  p_ix, r), r)
                cur_alpha_n = self._get_alpha_n(dist_matrix, p_ix, r)
                n_hat = np.mean(n_values)
                mdef = 1 - (cur_alpha_n / n_hat)
                sigma_mdef = np.std(n_values) / n_hat
                if n_hat >= 20:
                    outlier_scores[p_ix] = mdef / sigma_mdef
                    if mdef > (self.threshold_ * sigma_mdef):
                        break
        return outlier_scores

    def fit(self, X, y=None):
        """Fit the model using X as training data.
        
        Parameters
        ----------
        X : array, shape (n_samples, n_features)
            Training data.
            
        Returns
        -------
        self : object

        """
        X = check_array(X)
        self._set_n_classes(y)
        outlier_scores = self._calculate_decision_score(X)
        self.decision_scores_ = np.array(outlier_scores)
        self.labels_ = (self.decision_scores_ > self.threshold_).astype(
            'int').ravel()

        # calculate for predict_proba()

        self._mu = np.mean(self.decision_scores_)
        self._sigma = np.std(self.decision_scores_)
        return self

    def decision_function(self, X):
        check_is_fitted(self, ['decision_scores_', 'threshold_', 'labels_'])
        X = check_array(X)
        outlier_scores = self._calculate_decision_score(X)
        return np.array(outlier_scores)
