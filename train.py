import sys
import random
import math
import numpy as np
from PIL import Image
from time import sleep
from datetime import datetime, timedelta
from pyautogui import click, screenshot
from keras.models import Model, load_model, optimizers

from setting import TrainingSetting as set
from stepqueue import StepQueue
from directinputs import Keys
from QNet import QNet

class Train() :
    
    def __init__(self, use_weight_file = None) :
        
        self.GameRegion = set.get_game_region("Getting Over It")
        self.directInput = Keys()
        self.model_optimizer = optimizers.rmsprop(lr = 0.001) # decay = 1e-6)
        
        self.Q = QNet(set.model_input_shape, set.actions_num)
        self.Q.summary()
        self.Q.compile(loss = "mse", optimizer = self.model_optimizer, metrics = ['mse'])
        
        if use_weight_file :
            self.Q.load_weights(use_weight_file)
        
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
            
    def get_screenshot(self, wait_no_move = True, savefile = None) :
        array_scrshot = np.zeros(set.shot_shape)
        cur = screenshot(region = self.GameRegion).convert('RGB').resize(set.shot_resize)
        i = 0
        while(wait_no_move and i <= set.shot_wait_max) :
            i += 1
            #print("waiting for no moving")
            sleep(set.shot_intv_time)
            pre = cur
            cur = screenshot(region = self.GameRegion).convert('RGB').resize(set.shot_resize)
            if np.sum(np.array(cur)) < 256 :
                continue
            if np.sum(np.absolute((np.array(pre) - np.array(cur)) / 256.0)) < 33 * set.no_move_thrshld :
                break
        
        if set.shot_c == 1 :
            array_scrshot = np.reshape(np.array(cur.convert('L')) / 255.5, set.shot_shape)
        elif set.shot_c == 3 :
            array_scrshot[0] = np.array(cur) / 255.5
        else :
            raise Exception("shot_c isn't right.")
        if savefile : scrshot.save(savefile)
        return array_scrshot
    # end def get_screenshot
    
    def add_noise(self, noisy_scrshot) :
        noisy_scrshot += np.random.uniform(low = -set.noise_range, high = set.noise_range, size = noisy_scrshot.shape)
        noisy_scrshot[noisy_scrshot > 1.0] = 1.0
        noisy_scrshot[noisy_scrshot < 0.0] = 0.0
        return noisy_scrshot
    # end def get_screen_rect
    
    def do_control(self, id) :
        
        intv_time = 0.001
        
        if id < set.mouse_straight_angles * 2 :
            # is straight
            slow_distance = 2400 # pixels
            fast_distance = 4500 # pixels
            slow_delta = 3 # pixels
            fast_delta = 27
        
            if id < set.mouse_straight_angles :
                delta, distance = slow_delta, slow_distance
            else :
                delta, distance = fast_delta, fast_distance
            
            angle = 2 * math.pi * id / set.mouse_straight_angles
            d_x = math.ceil(math.cos(angle) * delta)
            d_y = math.ceil(math.sin(angle) * delta)
            
            for i in range(distance // delta) :
                self.directInput.directMouse(d_x, d_y)
                sleep(intv_time)
            if id >= set.mouse_straight_angles :
                sleep(0.02)
        else :
            # is round
            id -= set.mouse_straight_angles * 2
            
            if id < set.mouse_round_angles * 2 :
                is_clockwise = 1
            else :
                is_clockwise = -1
                id -= set.mouse_round_angles * 2
            
            if id < set.mouse_round_angles : # slow
                radius = 560
                delta = 4
                proportion = 0.8
            else : # fast
                radius = 700
                delta = 16
                proportion = 0.65
            
            circle_divide = 36.0
            angle_offset = 4.0
            edge_leng = int(2 * (radius**2) * (1 - math.cos(1.0 / circle_divide))) 
            
            for i in range(int(circle_divide * proportion)) : 
                angle = 2 * math.pi * (id / set.mouse_round_angles + ((i + angle_offset) / circle_divide))
                d_x = math.ceil(math.cos(angle) * delta) * is_clockwise
                d_y = math.ceil(math.sin(angle) * delta) * is_clockwise
                for j in range(edge_leng // delta) :
                    self.directInput.directMouse(d_x, d_y)
                    sleep(intv_time)
            sleep(0.01)
        sleep(set.do_control_pause)
    # end def do_control()
    
    def newgame(self) :
        sleep(1)
        # click "NEW GAME"
        click(self.GameRegion[0] + self.GameRegion[2] * 0.70, self.GameRegion[1] + self.GameRegion[3] * 0.40)
        sleep(8)
    
    def quitgame(self) :
        sleep(1)
        # push ESC
        self.directInput.directKey("ESC")
        sleep(1)
        # click "QUIT"
        click(self.GameRegion[0] + self.GameRegion[2] * 0.15, self.GameRegion[1] + self.GameRegion[3] * 1.05)
        sleep(10)
    
    def fit(self) :
        '''
        We will train Q, at time t, as:
            y_pred = Q([state_t, a_t])
            y_true = r_t + gamma * max(Q_target([state_t, for a in A]))
        update Q's weight in mse
        after a number of steps, copy Q to Q_target.
        '''
        
        stepQueue = StepQueue()
        
        for e in range(set.epoches) :
            
            self.newgame()
            
            this_epoch_eps = max(set.eps_min, set.epsilon * (set.eps_decay ** e), random.random())
            loss = 0

            for n in range(set.steps_epoch) :
                if (n + 1) % (set.steps_epoch / 10) == 0 :
                    sys.stdout.write(".")
                    sys.stdout.flush()
                
                cur_shot = self.get_screenshot(wait_no_move = False)

                # make action
                if random.random() < this_epoch_eps :
                    if n <= 1 :
                        cur_action = random.randrange(set.actions_num - 1)
                    else :
                        if set.use_p_normalizeation :
                            weight = stepQueue.getActionsOccurrence()
                            weight = weight.max() - weight
                            weight = weight / weight.sum()
                            cur_action = np.random.choice(np.arange(set.actions_num), p = weight)
                        else :
                            cur_action = np.random.choice(np.arange(set.actions_num))
                else :
                    cur_action = np.argmax(self.Q.predict(self.add_noise(cur_shot)))
                
                self.do_control(cur_action)
                
                nxt_shot = self.get_screenshot(wait_no_move = True)
                tmp_reward = stepQueue.calReward(cur_shot, nxt_shot) # pre-action, after-action
                
                #print(cur_action, ",", cur_reward)
                if tmp_reward == "stuck" :
                    sys.stdout.write(" at step " +  str(n) + ", ")
                    sys.stdout.flush()
                    break
                cur_reward = tmp_reward
                
                if set.ignore_zero_reward and random.random() >= (this_epoch_eps - set.eps_min) or cur_reward != 0 :
                    stepQueue.addStep(cur_shot, cur_action, cur_reward, nxt_shot)
                
                if (stepQueue.getLength() > set.train_size or n > set.train_thrshld) and n % set.steps_train == 0 :
                    # Experience Replay
                    random_step = random.randint(1, stepQueue.getLength() - set.train_size)
                    trn_cur_shot, trn_actions, trn_rewards, trn_nxt_shot = stepQueue.getStepsAsArray(random_step, set.train_size)
                    
                    # make next predicted reward array and train input array at same time
                    new_rewards = np.zeros((set.train_size, set.actions_num))
                    for j in range(set.train_size) :
                        # the j-th 
                        if set.steps_update_target > 0 :
                            new_rewards[j] = self.Q.predict(np.expand_dims(trn_nxt_shot[j], axis = 0))
                        else :
                            new_rewards[j] = self.Q_target.predict(np.expand_dims(trn_nxt_shot[j], axis = 0))
                        new_rewards[j, trn_actions[j]] = trn_rewards[j] + new_rewards[j, trn_actions[j]] * set.gamma
                        # Q_new = r + Q_predict(a,s) * gamma
                    
                    #print("new_rewards\n", new_rewards[0])
                    
                    loss += self.Q.train_on_batch(trn_cur_shot, new_rewards)[0] / set.steps_epoch
                    
                if set.steps_update_target > 0 and n % set.steps_update_target == 0 and n > set.train_thrshld :
                    #print("assign Qtarget")
                    self.Q_target.set_weights(self.Q.get_weights())
                    self.Q_target.save("Q_target_model.h5")
                    
            # end for(STEP_PER_EPOCH)
            
            print("end epoch", e, "of reward:", cur_reward, "loss:", loss)
            #stepQueue.clear()
            self.Q_target.save("Q_target_model.h5")
            # Restart Game...
            self.quitgame()
            
        # end for(epoches)
        
        self.Q_target.save("Q_target_model.h5")
        
    # end def fit
    
    def eval(self, model_weight_name, rounds = 1) :
        print("eval begin for:", model_weight_name)
        self.Q = load_model(model_weight_name)
        end_reward_list = []
        
        for i in range(rounds) :
        
            # click "NEW GAME"
            self.newgame()
            stepQueue = StepQueue()
            cur_shot = self.get_screenshot() 
            
            for n in range(set.steps_test) :
                cur_shot = self.get_screenshot()
                
                if random.random() <= set.eps_test :
                    cur_action = random.randrange(set.actions_num)
                    print("choose", cur_action, "as random")
                else :
                    predict_Q = np.squeeze(self.Q.predict(self.add_noise(cur_shot)))
                    
                    if predict_Q.sum() == 0 :
                        cur_action = random.randrange(set.actions_num)
                    else :
                        w = predict_Q - predict_Q.min()
                        w = w ** 2
                        w /= w.sum()
                        cur_action = np.random.choice(np.arange(set.actions_num), p = w)
                    
                    #cur_action = np.argmax(predict_Q)
                    #print(predict_Q)
                    print("choose", cur_action, "with higher Q:", predict_Q[cur_action])
                    
                self.do_control(cur_action)
                nxt_shot = self.get_screenshot()
            
            end_reward = stepQueue.calReward(cur_shot, self.get_screenshot())
            end_reward_list.append(end_reward)
            
            print("eval end, at reward of", end_reward)
            screenshot(region = self.GameRegion).save("eval_scrshot.png")
        
            # Exit Game...
            self.quitgame()
        
        print(end_reward_list)

    # end def eval
    
    def random_action(self, steps = None) :
        # click "NEW GAME"
        self.newgame()
        stepQueue = StepQueue()
        if steps == None : steps = set.steps_test
        for n in range(steps) :
            cur_shot = self.get_screenshot()
            cur_action = random.randrange(set.actions_num)
            self.do_control(cur_action)
            nxt_shot = self.get_screenshot()
            cur_reward = stepQueue.calReward(cur_shot, nxt_shot)
            print(cur_action, ",", cur_reward)
            if cur_reward == "stuck" :
                print("at step", n)
                screenshot(region = self.GameRegion).save("stuck_at_random.png")
                break
            stepQueue.addStep(cur_shot, cur_action, cur_reward, nxt_shot)
        
        del stepQueue
        print("eval end, of reward:", cur_reward)
        # Exit Game...
        self.quitgame()
    # end def
    
# end class Train

if __name__ == '__main__' :
    train = Train()
    train.count_down(3)
    starttime = datetime.now()
    train.random_action()
    #train.fit()
    print(datetime.now() - starttime)
    train.eval("Q_target_model.h5")
    

