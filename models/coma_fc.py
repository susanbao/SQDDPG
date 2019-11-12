import torch
import torch.nn as nn
import numpy as np
from utilities.util import *
from models.model import Model
from collections import namedtuple



class COMAFC(Model):

    def __init__(self, args, target_net=None):
        super(COMAFC, self).__init__(args)
        self.construct_model()
        self.apply(self.init_weights)
        if target_net != None:
            self.target_net = target_net
            self.reload_params_to_target()
        self.Transition = namedtuple('Transition', ('state', 'action', 'last_action', 'reward', 'next_state', 'done', 'last_step'))

    def unpack_data(self, batch):
        batch_size = len(batch.state)
        rewards = cuda_wrapper(torch.tensor(batch.reward, dtype=torch.float), self.cuda_)
        last_step = cuda_wrapper(torch.tensor(batch.last_step, dtype=torch.float).contiguous().view(-1, 1), self.cuda_)
        done = cuda_wrapper(torch.tensor(batch.done, dtype=torch.float).contiguous().view(-1, 1), self.cuda_)
        actions = cuda_wrapper(torch.tensor(np.stack(list(zip(*batch.action))[0], axis=0), dtype=torch.float), self.cuda_)
        last_actions = cuda_wrapper(torch.tensor(np.stack(list(zip(*batch.last_action))[0], axis=0), dtype=torch.float), self.cuda_)
        state = cuda_wrapper(prep_obs(list(zip(batch.state))), self.cuda_)
        next_state = cuda_wrapper(prep_obs(list(zip(batch.next_state))), self.cuda_)
        return (rewards, last_step, done, actions, last_actions, state, next_state)

    def construct_policy_net(self):
        h1 = nn.Linear(self.obs_dim+self.act_dim, self.hid_dim)
        h2 = nn.Linear(self.hid_dim, self.hid_dim)
        a = nn.Linear(self.hid_dim, self.act_dim)
        if self.args.shared_parameters:
            self.action_dict = nn.ModuleDict( {'layer_1': nn.ModuleList([ h1 for _ in range(self.n_)]),\
                                               'layer_2': nn.ModuleList([ h2 for _ in range(self.n_)]),\
                                               'action_head': nn.ModuleList([ a for _ in range(self.n_)])
                                              }
                                            )
        else:
            self.action_dict = nn.ModuleDict( {'layer_1': nn.ModuleList([nn.Linear(self.obs_dim+self.act_dim, self.hid_dim) for _ in range(self.n_)]),\
                                               'layer_2': nn.ModuleList([nn.Linear(self.hid_dim, self.hid_dim) for _ in range(self.n_)]),\
                                               'action_head': nn.ModuleList([nn.Linear(self.hid_dim, self.act_dim) for _ in range(self.n_)])
                                              }
                                            )

    def construct_value_net(self):
        if self.args.shared_parameters:
            l1 = nn.Linear( self.obs_dim*self.n_+self.act_dim*self.n_, self.hid_dim )
            l2 = nn.Linear(self.hid_dim, self.hid_dim)
            v = nn.Linear(self.hid_dim, self.act_dim)
            self.value_dict = nn.ModuleDict( {'layer_1': nn.ModuleList([ l1 for _ in range(self.n_)]),\
                                              'layer_2': nn.ModuleList([ l2 for _ in range(self.n_)]),\
                                              'value_head': nn.ModuleList([ v for _ in range(self.n_)])
                                             }
                                             )
        else:
            self.value_dict = nn.ModuleDict( {'layer_1': nn.ModuleList([nn.Linear( self.obs_dim*self.n_+self.act_dim*self.n_, self.hid_dim ) for _ in range(self.n_)]),\
                                              'layer_2': nn.ModuleList([nn.Linear(self.hid_dim, self.hid_dim) for _ in range(self.n_)]),\
                                              'value_head': nn.ModuleList([nn.Linear(self.hid_dim, self.act_dim) for _ in range(self.n_)])
                                             }
                                             )

    def construct_model(self):
        self.comm_mask = cuda_wrapper(torch.ones(self.n_, self.n_) - torch.eye(self.n_, self.n_), self.cuda_)
        self.construct_value_net()
        self.construct_policy_net()

    def policy(self, obs, schedule=None, last_act=None, last_hid=None, info={}, stat={}):
        batch_size = obs.size(0)
        inp = torch.cat( (obs, last_act), dim=-1 ) # shape = (b, n, o+a)
        actions = []
        hs = []
        for i in range(self.n_):
            h1 = torch.relu( self.action_dict['layer_1'][i](inp[:, i, :]) )
            h2 = torch.relu( self.action_dict['layer_2'][i](h1))
            a = self.action_dict['action_head'][i](h2)
            actions.append(a)
        actions = torch.stack(actions, dim=1)
        return actions

    def value(self, obs, act):
        batch_size = obs.size(0)
        act = act.unsqueeze(1).expand(batch_size, self.n_, self.n_, self.act_dim) # shape = (b, n, a) -> (b, 1, n, a) -> (b, n, n, a)
        comm_mask = self.comm_mask.unsqueeze(0).unsqueeze(-1).expand_as(act)
        act = act * comm_mask
        act = act.contiguous().view(batch_size, self.n_, -1) # shape = (b, n, a*n)
        obs = obs.unsqueeze(1).expand(batch_size, self.n_, self.n_, self.obs_dim).contiguous().view(batch_size, self.n_, -1) # shape = (b, n, o) -> (b, 1, n, o) -> (b, n, n, o)
        inp = torch.cat((obs, act), dim=-1) # shape = (b, n, o*n+a*n)
        values = []
        for i in range(self.n_):
            h = torch.relu( self.value_dict['layer_1'][i](inp[:, i, :]) )
            h = torch.relu( self.value_dict['layer_2'][i](h) )
            v = self.value_dict['value_head'][i](h)
            values.append(v)
        values = torch.stack(values, dim=1)
        return values

    def get_loss(self, batch):
        info = {}
        batch_size = len(batch.state)
        rewards, last_step, done, actions, last_actions, state, next_state = self.unpack_data(batch)
        action_out = self.policy(state, last_act=last_actions, info=info)
        values_ = self.value(state, actions)
        if self.args.q_func:
            values = torch.sum(values_*actions, dim=-1)
        values = values.contiguous().view(-1, self.n_)
        if self.args.target:
            next_action_out = self.target_net.policy(next_state, last_act=actions, info=info)
        else:
            next_action_out = self.policy(next_state, last_act=actions, info=info)
        next_actions = select_action(self.args, next_action_out, status='train', info=info, exploration=False)
        if self.args.target:
            next_values = self.target_net.value(next_state, next_actions)
        else:
            next_values = self.value(next_state, next_actions)
        if self.args.q_func:
            next_values = torch.sum(next_values*next_actions, dim=-1)
        next_values = next_values.contiguous().view(-1, self.n_)
        assert values.size() == next_values.size()
#         returns = self.td_lambda(rewards, last_step, done, next_values)
        returns = rewards + next_values * self.args.gamma
        assert returns.size() == rewards.size()
        deltas = returns - values
        advantages = ( values - torch.sum(values_*torch.softmax(action_out, dim=-1), dim=-1) ).detach()
        log_prob = multinomials_log_density(actions, action_out).contiguous().view(-1, 1)
        advantages = advantages.contiguous().view(-1, 1)
        if self.args.normalize_advantages:
            advantages = batchnorm(advantages)
        assert log_prob.size() == advantages.size()
        action_loss = - advantages * log_prob
        action_loss = action_loss.sum() / batch_size
        value_loss = deltas.pow(2).view(-1).sum() / batch_size
        return action_loss, value_loss, action_out


    def train_process(self, stat, trainer):
        info = {}
        state = trainer.env.reset()
        action = trainer.init_action
            
        if self.args.reward_record_type is 'episode_mean_step':
            trainer.mean_reward = 0
            trainer.mean_success = 0

        for t in range(self.args.max_steps):
            start_step = True if t == 0 else False
            state_ = cuda_wrapper(prep_obs(state).contiguous().view(1, self.n_, self.obs_dim), self.cuda_)
            action_ = action.clone()
            action_out = self.policy(state_, last_act=action_, info=info, stat=stat)
            action = select_action(self.args, torch.log_softmax(action_out, dim=-1), status='train', info=info)
            _, actual = translate_action(self.args, action, trainer.env)
            next_state, reward, done, debug = trainer.env.step(actual)
            if isinstance(done, list): done = np.sum(done)
            done_ = done or t==self.args.max_steps-1
            trans = self.Transition(state,
                                    action.cpu().numpy(),
                                    action_.cpu().numpy(),
                                    np.array(reward),
                                    next_state,
                                    done,
                                    done_
                                   )
            self.transition_update(trainer, trans, stat)
            success = debug['success'] if 'success' in debug else 0.0
            trainer.steps += 1
            if self.args.reward_record_type is 'mean_step':
                trainer.mean_reward = trainer.mean_reward + 1/trainer.steps*(np.mean(reward) - trainer.mean_reward)
                trainer.mean_success = trainer.mean_success + 1/trainer.steps*(success - trainer.mean_success)
            elif self.args.reward_record_type is 'episode_mean_step':
                trainer.mean_reward = trainer.mean_reward + 1/(t+1)*(np.mean(reward) - trainer.mean_reward)
                trainer.mean_success = trainer.mean_success + 1/(t+1)*(success - trainer.mean_success)
            else:
                raise RuntimeError('Please enter a correct reward record type, e.g. mean_step or episode_mean_step.')
            if done_:
                break
            state = next_state
        stat['turn'] = t+1
        stat['mean_reward'] = trainer.mean_reward
        stat['mean_success'] = trainer.mean_success
        trainer.episodes += 1

        return
