from collections import namedtuple
from multiagent.environment import MultiAgentEnv
import multiagent.scenarios as scenario
from utilities.gym_wrapper import *
import numpy as np
from aux import *


'''define the model name'''
model_name = 'coma_fc'

'''define the scenario name'''
scenario_name = 'simple_spread'

'''define the special property'''
# independentArgs = namedtuple( 'independentArgs', [] )
aux_args = AuxArgs[model_name]()
alias = '_new_1'

'''load scenario from script'''
scenario = scenario.load(scenario_name+".py").Scenario()

'''create world'''
world = scenario.make_world()

'''create multiagent environment'''
env = MultiAgentEnv(world, scenario.reset_world, scenario.reward, scenario.observation, info_callback=None, shared_viewer=True)
env = GymWrapper(env)

MergeArgs = namedtuple('MergeArgs', Args._fields+AuxArgs[model_name]._fields)

# under offline trainer if set batch_size=replay_buffer_size=update_freq -> epoch update
args = Args(model_name=model_name,
            agent_num=env.get_num_of_agents(),
            hid_size=64,
            obs_size=np.max(env.get_shape_of_obs()),
            continuous=False,
            action_dim=np.max(env.get_output_shape_of_act()),
            init_std=0.1,
            policy_lrate=1e-2,
            value_lrate=1e-2,
            max_steps=200,
            batch_size=100,
            gamma=0.95,
            normalize_advantages=False,
            entr=1e-2,
            entr_inc=0.0,
            action_num=np.max(env.get_input_shape_of_act()),
            q_func=True,
            train_episodes_num=int(1e5),
            replay=True,
            replay_buffer_size=1e6,
            replay_warmup=0,
            cuda=True,
            grad_clip=True,
            save_model_freq=1000,
            target=True,
            target_lr=1e-1,
            behaviour_update_freq=100,
            critic_update_times=10,
            target_update_freq=100,
            gumbel_softmax=False,
            epsilon_softmax=False,
            online=True,
            reward_record_type='episode_mean_step',
            shared_parameters=True
           )

args = MergeArgs(*(args+aux_args))

log_name = scenario_name + '_' + model_name + alias
