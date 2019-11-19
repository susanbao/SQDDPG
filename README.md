# Shapley Q-value: A Local Reward Approach to Solve Global Reward Games

## Dependencies
This project implements the algorithm of Shapley Q-value deep deterministic policy gradient (SQDDPG) mentioned in the paper:https://arxiv.org/abs/1907.05707 and demonstrates the experiments in comparison with Independent DDPG, Independent A2C, MADDPG and COMA.  

The code is running on Ubuntu 18.04 with Python (3.5.4) and Pytorch (1.0).

The suggestion is installing Anaconda 3 with Python (3.5.4): https://www.anaconda.com/download/.
To enable the experimantal environments, please install OpenAI Gym (0.10.5) and Numpy (1.14.5).
To use Tensorboard to monitor the training process, please install Tensorflow (r1.14).  
After installing the related dependencies mentioned above, open the terminal and execute the following bash script:
```bash
cd Shapley-Q-value-deep-deterministic-policy-gradient/environments/multiagent_particle_envs/
pip install -e .
```

Now, the dependencies for running the code are installed.

## Running Code for Experiments
The experiments on Cooperative Navigation and Prey-and-Predator mentioned in the paper are based on the environments from https://github.com/openai/multiagent-particle-envs, i.e., simple_spread and simple_tag. For convenience, we merge this repository to our framework with slight modifications on the scenario simple-tag.

About the experiment on Traffic Junction, the environment is from https://github.com/IC3Net/IC3Net/tree/master/ic3net-envs/ic3net_envs. To ease the life, we also add it to our framework.

### Training
To easily run the code for training, we provide argument files for each experiment with variant methods under the directory `args` and bash script to execute the experiment with different arguments.

For example, if we would like to run the experiment of simple_tag with the algorithm SQPG, we can edit the file `simple_tag_sqddpg.py` to change the hyperparameters. Then, we can edit `train.sh` to change the variable `EXP_NAME` to `"simple_tag_sqddpg"` and the variable `CUDA_VISIBLE_DEVICES` to the alias of the GPU you'd like to use, e.g. 0 here such that
```bash
# !/bin/bash
# sh train.sh

EXP_NAME="simple_tag_sqddpg"
ALIAS=""
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=0

if [ ! -d "./model_save" ]
then
  mkdir ./model_save
fi

mkdir ./model_save/$EXP_NAME$ALIAS
cp ./args/$EXP_NAME.py arguments.py
python -u train.py > ./model_save/$EXP_NAME$ALIAS/exp.out &
echo $! > ./model_save/$EXP_NAME$ALIAS/exp.pid
```

If necessary, we can also edit the variable `ALIAS` to ease the experiments with different hyperparameters.
Now, we only need to run the experiment by the bash script such that
```bash
source train.sh
```

### Testing
About testing, we provide a Python function called `test.py` which includes several arguments such that
```bash
--save-model-dir # the path to save the trained model
--render # whether the visualization is needed
--episodes # the number of episodes needed to run the test
```

### Experimental Results
See the paper: https://arxiv.org/abs/1907.05707.

## Extension of the Framework
This framework is easily to be extended by adding extra environments implemented in OpenAI Gym or new multi-agent algorithms implemented in Pytorch. To add extra algorithms, it just needs to inherit the base class `models/model.py` and implement the functions such that
```python
construct_model(self)
policy(self, obs, last_act=None, last_hid=None, gate=None, info={}, stat={})
value(self, obs, act)
construct_policy_net(self)
construct_value_net(self)
get_loss(self)
```

After implementing the class of your own methods, it needs to register your algorithm by the file `aux.py`. For example, if the algorithm is called sqddpg and the corresponding class is called `SQDDPG`, then the process of registeration is shown as below
```python
schednetArgs = namedtuple( 'sqddpgArgs', ['sample_size'] ) # define the exclusive hyperparameters of this algorithm
Model = dict(...,
             ...,
             ...,
             ...,
             sqddpg=SQDDPG
            ) # register the handle of the corresponding class of this algorithm
AuxArgs = dict(...,
               ...,
               ...,
               ...,
               sqddpg=sqddpgArgs
              ) # register the exclusive args of this algorithm
Strategy=dict(...,
              ...,
              ...,
              ...,
              sqddpg='pg'
             ) # register the training strategy of this algorithm, e.g., 'pg' or 'q'
```

Moreover, it is optional to define a restriction for your algorithm to avoid mis-defined hyperparameters in `utilities/inspector.py` such that
```python
if ... ...:
   ... ... ... ...
elif args.model_name is 'sqddpg':
      assert args.replay is True
      assert args.q_func is True
      assert args.target is True
      assert args.gumbel_softmax is True
      assert args.epsilon_softmax is False
      assert args.online is True
      assert hasattr(args, 'sample_size')
```

Finally, you can additionally add auxilliary functions in directory `utilities`.

Temporarily, this framework only supports the policy gradient methods. The functionality of value based method is under test and will be available soon.

## Citation
If you use the framework or part of the work mentioned in the paper, please cite:
```
@ARTICLE{2019arXiv190705707W,
       author = {{Wang}, Jianhong and {Zhang}, Yuan and {Kim}, Tae-Kyun and {Gu}, Yunjie},
        title = "{Shapley Q-value: A Local Reward Approach to Solve Global Reward Games}",
      journal = {arXiv e-prints},
     keywords = {Computer Science - Machine Learning, Computer Science - Artificial Intelligence, Computer Science - Multiagent Systems},
         year = "2019",
        month = "Jul",
          eid = {arXiv:1907.05707},
        pages = {arXiv:1907.05707},
archivePrefix = {arXiv},
       eprint = {1907.05707},
 primaryClass = {cs.LG},
       adsurl = {https://ui.adsabs.harvard.edu/abs/2019arXiv190705707W},
      adsnote = {Provided by the SAO/NASA Astrophysics Data System}
}
```
