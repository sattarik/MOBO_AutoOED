import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from algorithm.mobo.surrogate_model.base import SurrogateModel


class MLP(nn.Module):
    '''
    Multi-layer perceptron.
    '''
    def __init__(self, n_in, n_out, hidden_sizes, activation):
        '''
        Initialize a MLP neural network.

        Parameters
        ----------
        n_in: int
            Input dimension.
        n_out: int
            Output dimension.
        hidden_sizes: list
            List of sizes of hidden layers.
        activation: str
            Type of activation function, [relu, tanh] are supported.
        '''
        super().__init__()
        
        self.fc = nn.ModuleList()
        last_size = n_in
        for size in hidden_sizes:
            self.fc.append(nn.Linear(last_size, size))
            last_size = size
        self.fc.append(nn.Linear(last_size, n_out))

        ac_map = {
            'relu': torch.relu,
            'tanh': torch.tanh,
        }
        assert activation in ac_map, f"activation type {activation} doesn't supported"
        self.ac = ac_map[activation]

    def forward(self, x):
        for fc in self.fc[:-1]:
            x = self.ac(fc(x))
        x = self.fc[-1](x)
        return x

    def basis_func(self, x):
        for fc in self.fc[:-1]:
            x = self.ac(fc(x))
        return x


def jacobian(outputs, inputs, create_graph=False):
    '''
    Compute the jacobian of `outputs` with respect to `inputs`.
    NOTE: here the `outputs` and `inputs` are batched data, meaning that there's no correlation between individuals in a batch.

    Parameters
    ----------
    outputs: torch.tensor
        Outputs of neural networks.
    inputs: torch.tensor
        Inputs of neural networks.
    create_graph: bool, default=False
        Whether to create the computation graph.

    Returns
    -------
    torch.tensor
        Jacobian of outputs w.r.t. inputs.
    '''
    batch_size, output_shape, input_shape = outputs.shape[0], outputs.shape[1:], inputs.shape[1:]
    jacs = []
    for i in range(batch_size):
        for output in outputs[i].view(-1):
            jac = torch.autograd.grad(output, inputs, grad_outputs=None, allow_unused=True, retain_graph=True, create_graph=create_graph)[0][i]
            jacs.append(jac)
    return torch.stack(jacs).reshape((batch_size,) + output_shape + input_shape)


def hessian(outputs, inputs):
    '''
    Compute the hessian of `outputs` with respect to `inputs`.

    Parameters
    ----------
    outputs: torch.tensor
        Outputs of neural networks.
    inputs: torch.tensor
        Inputs of neural networks.

    Returns
    -------
    torch.tensor
        Hessian of outputs w.r.t. inputs.
    '''
    grad_inputs = jacobian(outputs, inputs, create_graph=True)
    return jacobian(grad_inputs, inputs)


class NeuralNetwork(SurrogateModel):
    '''
    Simple neural network
    '''
    def __init__(self, problem_cfg, hidden_sizes=(50, 50, 50), activation='tanh', lr=1e-3, weight_decay=1e-4, n_epoch=100, **kwargs):
        '''
        Initialize a neural network as surrogate model.

        Parameters
        ----------
        problem_cfg: dict
            Problem configurations.
        hidden_sizes: tuple, default=(50, 50, 50)
            Sizes of hidden layers of the neural network.
        activation: str, default='tanh'
            Type of activation function.
        lr: float, default=1e-3
            Learning rate.
        weight_decay: float, default=1e-4
            Weight decay.
        n_epoch: int, default=100
            Number of training epochs.
        '''
        super().__init__(problem_cfg)

        self.net = [MLP(n_in=n_var, n_out=1, hidden_sizes=hidden_sizes, activation=activation) for _ in range(n_obj)]
        self.criterion = nn.MSELoss()
        self.optimizer = [optim.Adam(net.parameters(), lr=lr, weight_decay=weight_decay) for net in self.net]
        self.n_epoch = n_epoch

    def _fit(self, X, Y):
        X, Y = torch.FloatTensor(X), torch.FloatTensor(Y)
        for i in range(self.n_obj):
            for _ in range(self.n_epoch):
                Y_pred = self.net[i](X)[:, 0]
                loss = self.criterion(Y_pred, Y[:, i])
                self.optimizer[i].zero_grad()
                loss.backward()
                self.optimizer[i].step()

    def _evaluate(self, X, std=False, calc_gradient=False, calc_hessian=False):
        F, dF, hF = [], [], []
        n_sample = X.shape[0] if len(X.shape) > 1 else 1
        X = torch.FloatTensor(X)
        X.requires_grad = True

        F = [self.net[i](X)[:, 0] for i in range(self.n_obj)]

        if calc_gradient:
            dF = [jacobian(f, X).numpy() for f in F]
        
        if calc_hessian:
            hF = [hessian(f, X).numpy() for f in F]

        F = [f.detach().numpy() for f in F]
        
        F = np.stack(F, axis=1)
        dF = np.stack(dF, axis=1) if calc_gradient else None
        hF = np.stack(hF, axis=1) if calc_hessian else None

        S = np.zeros((n_sample, self.n_obj)) if std else None
        dS = np.zeros((n_sample, self.n_obj, self.n_var)) if std and calc_gradient else None
        hS = np.zeros((n_sample, self.n_obj, self.n_var, self.n_var)) if std and calc_hessian else None
        
        out = {'F': F, 'dF': dF, 'hF': hF, 'S': S, 'dS': dS, 'hS': hS}
        return out
