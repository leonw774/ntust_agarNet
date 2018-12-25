import numpy as np
import math
from PIL import Image
from pyautogui import click, screenshot
from time import sleep
from setting import get_game_region, Setting as set
from directinputs import Keys

class GameAgent :
    
    GAME_REGION = get_game_region("Getting Over It")
    directInput = Keys()
    
    def get_screenshot(self, wait_no_move = True, savefile = None) :
        # return screen-shot of game in np array in shape of set.shot_shape
        array_scrshot = np.zeros(set.shot_shape)
        cur = screenshot(region = self.GAME_REGION).convert('RGB').resize(set.shot_resize)
        i = 0
        while(wait_no_move and i <= set.shot_wait_max) :
            #print("waiting for no moving")
            sleep(set.shot_intv_time)
            pre = cur
            cur = screenshot(region = self.GAME_REGION).convert('RGB').resize(set.shot_resize)
            if np.sum(np.array(cur)) <= 256 : # is black
                sleep(1.6)
                continue
            if np.sum(np.absolute((np.array(pre) - np.array(cur)) / 256.0)) < 33 * set.no_move_thrshld :
                break
            i += 1
        
        if set.shot_c == 1 :
            array_scrshot = np.reshape(np.array(cur.convert('L')) / 255.5, set.shot_shape)
        elif set.shot_c == 3 :
            array_scrshot[0] = np.array(cur) / 255.5
        else :
            raise Exception("shot_c isn't right.")
        if savefile : cur.save(savefile)
        return array_scrshot
    # end def get_screenshot
    
    def do_control(self, id) :
        
        intv_time = 0.001
        
        if id < set.mouse_straight_angles * 2 :
            # is straight
            slow_distance = 2400 # pixels
            fast_distance = 4000 # pixels
            slow_delta = 3 # pixels
            fast_delta = 20
        
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
                radius = 720
                delta = 20
                proportion = 0.7
            
            angles_divide = 36.0
            angle_bias = 4.0
            angle_offset = id / set.mouse_round_angles + angle_bias / angles_divide
            edge_leng = int(2 * (radius**2) * (1 - math.cos(1.0 / angles_divide))) 
            
            for i in range(int(angles_divide * proportion)) : 
                angle = 2 * math.pi * (i * is_clockwise / angles_divide + angle_offset)
                d_x = math.ceil(math.cos(angle) * delta)
                d_y = math.ceil(math.sin(angle) * delta)
                for j in range(edge_leng // delta) :
                    self.directInput.directMouse(d_x, d_y)
                    sleep(intv_time)
            sleep(0.01)
        sleep(set.do_control_pause)
    # end def do_control()
    
    def newgame(self) :
        sleep(1)
        # click "NEW GAME"
        while(1) : # sometimes the game is not responsive to keybroad, you have to try more times
            shot1 = np.array(screenshot(region = self.GAME_REGION).convert('RGB').resize(set.shot_resize))
            click(self.GAME_REGION[0] + self.GAME_REGION[2] * 0.70, self.GAME_REGION[1] + self.GAME_REGION[3] * 0.36)
            sleep(0.2)
            shot2 = np.array(screenshot(region = self.GAME_REGION).convert('RGB').resize(set.shot_resize))
            if np.sum(np.abs(shot1 - shot2)) > set.no_move_thrshld : break
        sleep(7.5)
    
    def quitgame(self) :
        sleep(1)
        # push ESC
        while(1) : # sometimes the game is not responsive to keybroad, you have to try more times
            shot1 = np.array(screenshot(region = self.GAME_REGION).convert('RGB').resize(set.shot_resize))
            self.directInput.directKey("ESC")
            sleep(0.2)
            shot2 = np.array(screenshot(region = self.GAME_REGION).convert('RGB').resize(set.shot_resize))
            if np.sum(np.abs(shot1 - shot2)) > set.no_move_thrshld : break
        # click "QUIT"
        click(self.GAME_REGION[0] + self.GAME_REGION[2] * 0.15, self.GAME_REGION[1] + self.GAME_REGION[3] * 1.05)
        sleep(10)
    