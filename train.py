import random
import math
import numpy as np
from PIL import Image
from time import sleep
from pyautogui import click, screenshot
from keras.models import Model

from setting import TrainingSetting as set
from setting import GameRegion
from statequeue import StateQueue
from directinputs import Keys
from QNet import QNet

class Train() :
    
    def __init__(self) :
        self.directInput = Keys()
        self.Q = QNet(set.model_input_shape, set.actions_num)
        self.Q.summary()
        self.Q.compile(loss = "mse", optimizer = set.model_optimizer)
        if set.steps_update_target > 0 :
            self.Q_target = QNet(set.model_input_shape, set.actions_num)
            self.Q_target.set_weights(self.Q.get_weights())
        self.A = []
        for i in range(set.actions_num) :
            action_onehot = np.zeros((1, set.actions_num))
            action_onehot[0, i] = 1
            self.A.append(action_onehot)
    
    def count_down(self, cd) :
        for i in range(cd) :
            print(cd - i)
            sleep(1.0)
            
    def get_screenshot(self, savefile = None) :
        sleep(set.scrshot_intv_time)
        array_scrshot = np.zeros(set.scrshot_shape)
        while(True) :
            if set.color_size == 1 :
                scrshot = (screenshot(region = GameRegion)).convert('L').resize(set.scrshot_resize, resample = Image.NEAREST)
                array_scrshot = np.reshape(np.array(scrshot) / 255.5, set.scrshot_shape)
            elif set.color_size == 3 :
                scrshot = (screenshot(region = GameRegion)).convert('RGB').resize(set.scrshot_resize, resample = Image.NEAREST)
                array_scrshot[0] = np.array(scrshot) / 255.5
            else :
                raise Exception("color_size isn't right.")
            if savefile : scrshot.save(savefile)
            if np.sum(array_scrshot) < 0.001 :
                sleep(1.0)
            else :
                return array_scrshot
    # end def get_screenshot
    
    def add_noise(self, noisy_scrshot) :
        noisy_scrshot += np.random.uniform(low = -set.noise_range, high = set.noise_range, size = set.scrshot_shape)
        noisy_scrshot[noisy_scrshot > 1.0] = 1.0
        noisy_scrshot[noisy_scrshot < 0.0] = 0.0
        return noisy_scrshot
    # end def get_screen_rect
    
    def do_control(self, id) : 
        '''
        相對方向的滑動
        未來或許可以嘗試在ActionSet中加入控制快慢和距離的選擇
        [slow moving x angle_num, fast moving x angle_num]
        '''
        slow_distance = 3200 # pixels
        fast_distance = 8000 # pixels
        slow_intv = 8 # pixels
        fast_intv = 32
        intv_time = 0.0032
        
        if id < set.mouse_angle_devision :
            intv, distance = slow_intv, slow_distance
        else :
            intv, distance = fast_intv, fast_distance
        
        angle = 2 * math.pi * id / set.mouse_angle_devision
        offset_x = math.ceil(math.cos(angle) * intv)
        offset_y = math.ceil(math.sin(angle) * intv)
        
        for i in range(distance // intv) :
            self.directInput.directMouse(offset_x, offset_y)
            sleep(intv_time)
        sleep(set.do_control_pause)
    # end def do_control()
    
    def run(self) :
        '''
        We would train Q, at time t, as:
            y_pred = Q([state_t, a_t])
            y_true = r_t + gamma * max(Q_target([state_t, for a in A]))
        update Q's weight in mse
        after a number of steps, copy Q to Q_target.
        '''
        for e in range(set.epoches) :
            
            # click "NEW GAME"
            click(GameRegion[0] + GameRegion[2] * 0.66, GameRegion[1] + GameRegion[3] * 0.36)
            sleep(7)
            
            stateQueue = StateQueue()

            for n in range(set.steps_epoch) :
            
                # make action
                cur_shot = self.get_screenshot()
                if random.random() < max(set.eps_min, set.epsilon * (set.eps_decay ** e)):
                    cur_action = random.randrange(set.actions_num)
                    #print(np.argmax(self.Q.predict(self.add_noise(cur_shot))))
                else :
                    cur_action = np.argmax(self.Q.predict(self.add_noise(cur_shot)))
                    #print(cur_action)
                
                self.do_control(cur_action)
                
                nxt_shot = self.get_screenshot()
                cur_reward = stateQueue.calReward(cur_shot, nxt_shot)
                print(cur_action, ",", cur_reward)
                
                stateQueue.addStep(cur_shot, cur_action, cur_reward, nxt_shot)
                
                if stateQueue.getLength() > set.train_size and n > set.train_thrshld and n % set.steps_train == 0 :
                    # Experience Replay
                    r = random.randint(0, stateQueue.getLength() - set.train_size)
                    input_scrshots, input_actions, rewards, train_nxt_shots = stateQueue.getStepsInArray(r, set.train_size)
                    
                    # make replay reward array
                    replay_rewards = np.zeros((set.train_size, set.actions_num))
                    for j in range(set.train_size) :
                        replay_rewards[j, int(input_actions[j])] = rewards[j]
                    
                    # make next predicted reward array
                    nxt_rewards = np.zeros((set.train_size, set.actions_num))
                    
                    for j in range(set.train_size) :
                        this_nxt_shots = np.reshape(train_nxt_shots[j], set.scrshot_shape)
                        #print(input_actions[j])
                        if set.steps_update_target > 0 :
                            nxt_rewards[j] = self.Q.predict(self.add_noise(this_nxt_shots))
                            nxt_rewards[j, int(input_actions[j])] = np.argmax(self.Q.predict(self.add_noise(this_nxt_shots)))
                        else :
                            nxt_rewards[j] = self.Q_target.predict(self.add_noise(this_nxt_shots))
                            nxt_rewards[j, int(input_actions[j])] = np.argmax(self.Q_target.predict(self.add_noise(this_nxt_shots)))
                        
                    train_targets = np.add(replay_rewards, np.multiply(set.gamma, nxt_rewards))
                    
                    #print("replay_rewards\n", replay_rewards[0])
                    #print("nxt_rewards\n", nxt_rewards[0])
                    #print("train_targets\n", train_targets[0])
                    
                    loss = self.Q.train_on_batch(input_scrshots, train_targets)
                    #print("loss: ", loss)
                    
                if set.steps_update_target > 0 and n % set.steps_update_target == 0 and n != 0 :
                    print("assign Qtarget")
                    self.Q_target.set_weights(self.Q.get_weights())
                    self.Q_target.save_weights("Q_target_weight.h5")
                    
                # end for(STEP_PER_EPOCH)  
            print("end epoch", e)
            del stateQueue
            
            # Restart Game...
            sleep(0.1)
            # push ESC
            self.directInput.directKey("ESC")
            sleep(0.1)
            # click "QUIT"
            click(GameRegion[0] + GameRegion[2] * 0.21, GameRegion[1] + GameRegion[3] * 0.96)
            sleep(7)
            
        # end for(epoches)
        
        self.Q_target.save_weights("Q_target_weight.h5")
        
    # end def run
    
    def eval(self, model_weight_name) :
        print("eval begin for:", model_weight_name)
        self.Q.load_weights(model_weight_name)
        
        # click "NEW GAME"
        click(GameRegion[0] + GameRegion[2] * 0.66, GameRegion[1] + GameRegion[3] * 0.36)
        sleep(7)
        
        totalReward = 0
        
        for n in range(set.steps_test) :
            cur_shot = self.get_screenshot()
            if random.random() < set.eps_test :
                cur_action = random.randrange(set.actions_num)
            else :
                cur_action = np.argmax(self.Q.predict(self.add_noise(cur_shot)))

            self.do_control(cur_action)
        
        screenshot(region = GameRegion).save("eval_scrshot.png")
        
        # Exit Game...
        # push ESC
        self.directInput.directKey("ESC")
        sleep(0.1)
        # click "QUIT"
        click(GameRegion[0] + GameRegion[2] * 0.21, GameRegion[1] + GameRegion[3] * 0.96)

    # end def eval
    
    def random_action(self, times) :
        # click "NEW GAME"
        click(GameRegion[0] + GameRegion[2] * 0.66, GameRegion[1] + GameRegion[3] * 0.36)
        sleep(7)
        for n in range(times) :
            self.do_control(random.randrange(set.actions_num))
        # Exit Game...
        # push ESC
        self.directInput.directKey("ESC")
        sleep(0.1)
        # click "QUIT"
        click(GameRegion[0] + GameRegion[2] * 0.21, GameRegion[1] + GameRegion[3] * 0.96)
    # end def
    
# end class Train

if __name__ == '__main__' :
    train = Train()
    train.count_down(3)
    train.run()
    train.eval("Q_target_weight.h5")
    

