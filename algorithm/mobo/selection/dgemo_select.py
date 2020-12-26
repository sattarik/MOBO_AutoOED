from .base import Selection


class DGEMOSelect(Selection):
    '''
    Selection method for DGEMO algorithm
    '''
    has_family = True

    def select(self, solution, surrogate_model, status, transformation):
        algo = solution['algo']

        X_next, _, family_lbls_next = algo.propose_next_batch(status['pfront'], self.ref_point, self.batch_size, transformation)
        family_lbls, approx_pset, approx_pfront = algo.get_sparse_front(transformation)

        info = {
            'family_lbls_next': family_lbls_next,
            'family_lbls': family_lbls,
            'approx_pset': approx_pset,
            'approx_pfront': approx_pfront,
        }
        return X_next, info