import torch
from torch import nn
import pytorch_lightning as pl
from sindy_autoencoder_cps.sindy_library import SINDyLibrary
pl.seed_everything(12354)





class Encoder(nn.Module):
    def __init__(self, input_dim=10000, hidden_size=10000, enc_out_dim=3, activation=nn.ReLU(), *args, **kwargs):
        super(Encoder, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, enc_out_dim)
        self.activation = activation

    def forward(self, x):
        out = self.activation(self.fc1(x))
        out = self.activation(self.fc2(out))
        out = self.fc3(out)
        return out

class Decoder(nn.Module):
    def __init__(self, input_dim=3, hidden_size=10000, dec_output_dim=10000, activation=nn.ReLU(), *args, **kwargs):
        super(Decoder, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_size)
        self.fc2 = nn.Linear(hidden_size, hidden_size)
        self.fc3 = nn.Linear(hidden_size, dec_output_dim)
        self.activation = activation

    def forward(self, x):
        out = self.activation(self.fc1(x))
        out = self.activation(self.fc2(out))
        out = self.fc3(out)
        return out


class SINDyAutoencoder(pl.LightningModule):
    def __init__(self, learning_rate=.001, network_hidden_size=10000, input_dim=10000, 
                 latent_dim=3,
                 activation='relu',
                 sindy_biases=True,
                 sindy_states=True,
                 sindy_sin=False,
                 sindy_cos=False,
                 sindy_multiply_pairs=True,
                 sindy_poly_order=2,
                 sindy_sqrt=False,
                 sindy_inverse=False,
                 sindy_sign_sqrt_of_diff=True,
                 sequential_thresholding=True,
                 loss_weight_sindy_x = 1,
                 loss_weight_sindy_z = 1,
                 loss_weight_sindy_regularization = 1,
                 *args, **kwargs):
        super().__init__()
        self.learning_rate = learning_rate
        self.save_hyperparameters()
        self.num_layers = 3
        self.activation_function_str = activation
        if activation == 'relu':
            self.activation_function = nn.ReLU()
        elif activation == 'sigmoid':
            self.activation_function = nn.Sigmoid()
        elif activation == 'tanh':
            self.activation_function = nn.Tanh()
        else:
            print('nooooo!')

        self.phi_x = Encoder(input_dim=input_dim,
                             hidden_size=network_hidden_size,
                             enc_out_dim=latent_dim,
                             activation=self.activation_function)
        self.psi_z = Decoder(input_dim=latent_dim,
                             hidden_size=network_hidden_size,
                             dec_output_dim=input_dim,
                             activation=self.activation_function)
        self.SINDyLibrary = SINDyLibrary(
                 device='cuda:0',
                 latent_dim=latent_dim,
                 include_biases=sindy_biases,
                 include_states=sindy_states,
                 include_sin=sindy_sin,
                 include_cos=sindy_cos,
                 include_multiply_pairs=sindy_multiply_pairs,
                 poly_order=sindy_poly_order,
                 include_sqrt=sindy_sqrt,
                 include_inverse=sindy_inverse,
                 include_sign_sqrt_of_diff=sindy_sign_sqrt_of_diff)


        self.XI = nn.Parameter(torch.full((self.SINDyLibrary.number_candidate_functions, latent_dim), .1))

        self.sequential_thresholding = sequential_thresholding
        self.XI_coefficient_mask = torch.ones((self.SINDyLibrary.number_candidate_functions, latent_dim))

        self.loss_weight_sindy_x = loss_weight_sindy_x
        self.loss_weight_sindy_z = loss_weight_sindy_z
        self.loss_weight_sindy_regularization = loss_weight_sindy_regularization
        self.loss_names = ['total_loss', 'recon_loss', 'sindy_loss_x', 'sindy_loss_z', 'sindy_regular_loss']

    def configure_optimizers(self):
        return torch.optim.Adam(self.parameters(), lr=self.learning_rate)

    def loss_function(self, x, xdot, x_hat, xdot_hat, zdot, zdot_hat, XI):
        mse = nn.MSELoss()
        recon_loss = mse(x, x_hat)
        sindy_loss_x = mse(xdot, xdot_hat)
        sindy_loss_z = mse(zdot, zdot_hat)
        sindy_regular_loss = torch.sum(torch.abs(XI))
        loss =  recon_loss +  self.loss_weight_sindy_x * sindy_loss_x \
            + self.loss_weight_sindy_z * sindy_loss_z \
            + self.loss_weight_sindy_regularization * sindy_regular_loss 
        return loss, recon_loss, sindy_loss_x, sindy_loss_z, sindy_regular_loss

    def compute_nn_derivates_wrt_time(self, y, ydot, weights_list, biases_list, activation='relu'):
        y_l = y
        ydot_l = ydot 
        for l in range(len(weights_list) -1):
            # help variable
            hv = torch.matmul(y_l, weights_list[l].T) + biases_list[l]
            #  forward to get y_l for next layer
            if activation=='relu':
                y_l = torch.nn.ReLU()(hv)
                # compute ydot for next layer l (this layer) using hv (so also y_l) and ydot_l
                ydot_l = (hv > 0).float() *  torch.matmul(ydot_l, weights_list[l].T)
            elif activation == 'sigmoid':
                y_l = torch.nn.Sigmoid()(hv)
                ydot_l = y_l * (1-y_l) *  torch.matmul(ydot_l, weights_list[l].T)
            elif activation == 'tanh':
                y_l = torch.nn.Tanh()(hv)
                ydot_l = (1 - torch.square(torch.tanh(hv))) *  torch.matmul(ydot_l, weights_list[l].T)
        ydot_l = torch.matmul(ydot_l, weights_list[-1].T)
        return ydot_l

    def forward(self, x, xdot):
        return self._shared_eval(x, xdot)

    def _shared_eval(self, x, xdot):
        z = self.phi_x(x)
        x_hat = self.psi_z(z)
        theta = self.SINDyLibrary.transform(z)
        zdot_hat = torch.matmul(theta, self.XI)
        phi_x_parameters = list(self.phi_x.parameters())
        phi_x_weight_list = [w for w in phi_x_parameters if len(w.shape) == 2]
        phi_x_biases_list = [b for b in phi_x_parameters if len(b.shape) == 1] 
        zdot = self.compute_nn_derivates_wrt_time(x, xdot, phi_x_weight_list, phi_x_biases_list, activation=self.activation_function_str)
        psi_z_parameters = list(self.psi_z.parameters())
        psi_z_weight_list = [w for w in psi_z_parameters if len(w.shape) == 2]
        psi_z_biases_list = [b for b in psi_z_parameters if len(b.shape) == 1] 
        xdot_hat = self.compute_nn_derivates_wrt_time(z, zdot, psi_z_weight_list, psi_z_biases_list, activation=self.activation_function_str) 
        return x_hat, xdot_hat, z, zdot, zdot_hat  


    def training_step(self, batch, batch_idx):
        x, xdot, _ = batch
        x_hat, xdot_hat, z, zdot, zdot_hat = self._shared_eval(x, xdot)
        losses = self.loss_function(x=x, xdot=xdot, x_hat=x_hat, xdot_hat=xdot_hat,
                                  zdot=zdot, zdot_hat=zdot_hat, XI=self.XI) 
        loss_dict = dict(zip([f'train_{n}' for n in self.loss_names], losses))
        self.logger.experiment.add_scalars("loss", loss_dict)
        return loss_dict['train_total_loss']

    def validation_step(self, batch, batch_idx):
        x, xdot, _ = batch
        x_hat, xdot_hat, z, zdot, zdot_hat = self._shared_eval(x, xdot)
        losses = self.loss_function(x=x, xdot=xdot, x_hat=x_hat, xdot_hat=xdot_hat,
                                  zdot=zdot, zdot_hat=zdot_hat, XI=self.XI) 
        loss_dict = dict(zip([f'val_{n}' for n in self.loss_names], losses))
        self.logger.experiment.add_scalars("loss", loss_dict)
        return loss_dict['val_total_loss']



