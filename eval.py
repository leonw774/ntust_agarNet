from setting import GameRegion
from setting import TrainingSetting as set
from train import Train

train = Train()
train.count_down(3)
train.eval("Q_target_weight.h5")