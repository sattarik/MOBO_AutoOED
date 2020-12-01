import os
import shutil
import yaml
from time import time, sleep
from datetime import datetime
import numpy as np

from config.utils import load_config, process_config
from problem.common import build_problem, get_initial_samples
from problem.problem import Problem

import tkinter as tk
from tkinter import messagebox
from system.scientist.gui.view import ScientistLoginView, ScientistView
from system.server.db_team import Database
from system.server.agent import DataAgent, WorkerAgent
from system.scientist.gui.params import *

from system.scientist.gui.menu_file import MenuFileController
from system.scientist.gui.menu_config import MenuConfigController
from system.scientist.gui.menu_problem import MenuProblemController
from system.scientist.gui.menu_database import MenuDatabaseController
from system.scientist.gui.menu_eval import MenuEvalController
from system.scientist.gui.panel_control import PanelControlController
from system.scientist.gui.panel_log import PanelLogController
from system.scientist.gui.viz_space import VizSpaceController
from system.scientist.gui.viz_stats import VizStatsController
from system.scientist.gui.viz_database import VizDatabaseController


class ScientistController:

    def __init__(self):
        self.root_login = tk.Tk()
        self.root_login.title('OpenMOBO - Scientist')
        self.root_login.protocol('WM_DELETE_WINDOW', self._quit_login)
        self.root_login.resizable(False, False)
        self.view_login = ScientistLoginView(self.root_login)
        self.bind_command_login()

        self.root = None
        self.view = None
        self.after_handle = None
        
        self.database = None
        self.table_name = None

        self.table_checksum = None

    def bind_command_login(self):
        '''
        '''
        self.view_login.widget['login'].configure(command=self.login_database)

    def login_database(self):
        '''
        '''
        try:
            ip = self.view_login.widget['ip'].get()
            user = self.view_login.widget['user'].get()
            passwd = self.view_login.widget['passwd'].get()
            table = self.view_login.widget['table'].get()
        except Exception as e:
            messagebox.showinfo('Error', e, parent=self.root_login)
            return

        try:
            self.database = Database(ip, user, passwd)
        except:
            messagebox.showinfo('Error', 'Invalid IP or username or password', parent=self.root_login)
            return

        if not (self.database.check_table_exist(table) or self.database.check_empty_table_exist(table)):
            messagebox.showinfo('Error', f"Table {table} doesn't exist", parent=self.root_login)
            return     

        self.after_login(table_name=table)

    def _quit_login(self):
        '''
        Quit handling for login window
        '''
        self.root_login.quit()
        self.root_login.destroy()

    def after_login(self, table_name):
        '''
        '''
        self._quit_login()

        self.table_name = table_name

        self.root = tk.Tk()
        self.root.title('OpenMOBO - Scientist')
        self.root.protocol('WM_DELETE_WINDOW', self._quit)

        # TODO: use customized theme
        # from tkinter import ttk
        # from system.utils.path import get_root_dir
        # self.root.tk.call('lappend', 'auto_path', os.path.join(get_root_dir(), 'system', 'gui', 'themes'))
        # self.root.tk.call('package', 'require', 'awdark')
        # s = ttk.Style()
        # s.theme_use('awdark')

        self.refresh_rate = REFRESH_RATE # ms
        self.result_dir = RESULT_DIR # initial result directory
        self.config = None
        self.config_raw = None
        self.config_id = -1
        self.problem_cfg = None
        self.timestamp = None

        self.data_agent = DataAgent(self.database, self.table_name)
        self.worker_agent = WorkerAgent(self.data_agent)

        self.true_pfront = None

        self.n_sample = None
        self.n_valid_sample = None

        self.view = ScientistView(self.root)
        self.controller = {}

        self._init_menu()
        self._init_panel()

        self.root.mainloop()
    
    def _init_menu(self):
        '''
        Menu initialization
        '''
        self.controller['menu_file'] = MenuFileController(self)
        self.view.menu_file.entryconfig(0, command=self.controller['menu_file'].set_result_dir)

        self.controller['menu_config'] = MenuConfigController(self)
        self.view.menu_config.entryconfig(0, command=self.controller['menu_config'].load_config_from_file)
        self.view.menu_config.entryconfig(1, command=self.controller['menu_config'].create_config)
        self.view.menu_config.entryconfig(2, command=self.controller['menu_config'].change_config, state=tk.DISABLED)

        self.controller['menu_problem'] = MenuProblemController(self)
        self.view.menu_problem.entryconfig(0, command=self.controller['menu_problem'].manage_problem)

        self.controller['menu_database'] = MenuDatabaseController(self)
        self.view.menu_database.entryconfig(0, command=None, state=tk.DISABLED) # TODO
        self.view.menu_database.entryconfig(1, command=self.controller['menu_database'].export_csv, state=tk.DISABLED)
        self.view.menu_database.entryconfig(2, command=self.controller['menu_database'].enter_design, state=tk.DISABLED)
        self.view.menu_database.entryconfig(3, command=self.controller['menu_database'].enter_performance, state=tk.DISABLED)

        self.controller['menu_eval'] = MenuEvalController(self)
        self.view.menu_eval.entryconfig(0, command=self.controller['menu_eval'].start_local_eval, state=tk.DISABLED)
        self.view.menu_eval.entryconfig(1, command=None, state=tk.DISABLED) # TODO
        self.view.menu_eval.entryconfig(2, command=self.controller['menu_eval'].stop_eval, state=tk.DISABLED)

    def _init_panel(self):
        '''
        Panel initialization
        '''
        self.controller['panel_control'] = PanelControlController(self)
        self.controller['panel_log'] = PanelLogController(self)

    def _init_visualization(self):
        '''
        Visualization initialization
        '''
        self.controller['viz_space'] = VizSpaceController(self)
        self.controller['viz_stats'] = VizStatsController(self)
        self.controller['viz_database'] = VizDatabaseController(self)
        self.view.activate_viz()

    def _load_existing_data(self):
        '''
        '''
        # load table data
        self.controller['viz_database'].update_data(opt_done=True, eval_done=False)

        # load viz status
        self.controller['viz_space'].redraw_performance_space(reset_scaler=True)
        self.controller['viz_stats'].redraw()

    def get_config(self):
        return self.config

    def get_config_id(self):
        return self.config_id

    def get_problem_cfg(self):
        return self.problem_cfg

    def set_config(self, config, window=None):
        '''
        Setting configurations
        '''
        # set parent window for displaying potential error messagebox
        if window is None: window = self.root

        try:
            config = process_config(config)
        except Exception as e:
            tk.messagebox.showinfo('Error', 'Invalid configurations: ' + str(e), parent=window)
            return False

        # update raw config (config will be processed and changed later)
        self.config_raw = config.copy()
        
        old_config = None if self.config is None else self.config.copy()

        if self.config is None: # first time setting config
            # create directory for saving results
            if not self.create_result_dir(window):
                return False

            # initialize problem
            try:
                problem, self.true_pfront = build_problem(config['problem'], get_pfront=True)
            except Exception as e:
                tk.messagebox.showinfo('Error', 'Invalid values in configuration: ' + str(e), parent=window)
                return False

            # check if config is compatible with history data (problem dimension)
            table_exist = self.database.check_table_exist(self.table_name)
            if table_exist:
                column_names = self.database.get_column_names(self.table_name)
                data_n_var = len([name for name in column_names if name.startswith('x')])
                data_n_obj = len([name for name in column_names if name.startswith('y') and '_' not in name])
                try:
                    assert problem.n_var == data_n_var and problem.n_obj == data_n_obj
                except:
                    tk.messagebox.showinfo('Error', 'Problem dimension mismatch between configuration and history data', parent=window)
                    return False

            # update config
            self.config = config
            self.problem_cfg = problem.get_config(
                var_lb=config['problem']['var_lb'],
                var_ub=config['problem']['var_ub'],
                obj_lb=config['problem']['obj_lb'],
                obj_ub=config['problem']['obj_ub'],
            )

            # remove tutorial image
            self.view.image_tutorial.destroy()

            # TODO: give hint of initializing

            # configure agents
            self.data_agent.configure(n_var=problem.n_var, n_obj=problem.n_obj, minimize=problem.minimize)
            self.worker_agent.configure(mode='manual', config=config, config_id=0, eval=hasattr(problem, 'evaluate_performance'))

            self.data_agent.init_table(create=not table_exist)

            if not table_exist:
                # data initialization
                X_init_evaluated, X_init_unevaluated, Y_init_evaluated = get_initial_samples(config['problem'], problem)
                if X_init_evaluated is not None:
                    self.data_agent.init_data(X_init_evaluated, Y_init_evaluated)
                if X_init_unevaluated is not None:
                    rowids = self.data_agent.init_data(X_init_unevaluated)
                    for rowid in rowids:
                        self.worker_agent.add_eval_worker(rowid)
                    
                    # wait until initialization is completed
                    while not self.worker_agent.empty():
                        self.worker_agent.refresh()
                        sleep(self.refresh_rate / 1000.0)

            # calculate reference point
            if self.config['problem']['ref_point'] is None:
                Y = self.data_agent.load('Y', dtype=float)
                valid_idx = np.where((~np.isnan(Y)).all(axis=1))[0]
                Y = Y[valid_idx]
                ref_point = np.zeros(problem.n_obj)
                for i, m in enumerate(problem.minimize):
                    if m == True:
                        ref_point[i] = np.max(Y[:, i])
                    else:
                        ref_point[i] = np.min(Y[:, i])
                self.config['problem']['ref_point'] = ref_point

            # initialize visualization widgets
            self._init_visualization()

            # load existing data
            if table_exist:
                self._load_existing_data()

            # disable changing saving location
            self.view.menu_file.entryconfig(0, state=tk.DISABLED)

            # change config create/change status
            self.view.menu_config.entryconfig(1, state=tk.DISABLED)
            self.view.menu_config.entryconfig(2, state=tk.NORMAL)

            for i in range(4):
                self.view.menu_database.entryconfig(i, state=tk.NORMAL)
            
            for i in range(3):
                self.view.menu_eval.entryconfig(i, state=tk.NORMAL)

            # activate widgets
            entry_mode = self.controller['panel_control'].view.widget['mode']
            entry_mode.enable(readonly=False)
            entry_mode.set('manual')
            entry_mode.enable(readonly=True)

            entry_batch_size = self.controller['panel_control'].view.widget['batch_size']
            entry_batch_size.enable()
            try:
                entry_batch_size.set(self.config['general']['batch_size'])
            except:
                entry_batch_size.set(5)

            entry_n_iter = self.controller['panel_control'].view.widget['n_iter']
            entry_n_iter.enable()
            try:
                entry_n_iter.set(self.config['general']['n_iter'])
            except:
                entry_n_iter.set(1)

            self.controller['panel_control'].view.widget['optimize'].enable()
            self.controller['panel_control'].view.widget['set_stop_cri'].enable()

            self.controller['panel_log'].view.widget['clear'].enable()

            # trigger periodic refresh
            self.after_handle = self.root.after(self.refresh_rate, self.refresh)

        else: # user changed config in the middle
            try:
                # some keys cannot be changed
                unchanged_keys = ['name', 'n_init_sample', 'init_sample_path']
                if self.config_raw['problem']['ref_point'] is not None:
                    unchanged_keys.append('ref_point')
                for key in unchanged_keys:
                    assert (np.array(self.config_raw['problem'][key]) == np.array(config['problem'][key])).all()
            except:
                tk.messagebox.showinfo('Error', 'Invalid configuration values for reloading', parent=window)
                return False

            self.config = config
            self.problem_cfg = Problem.process_config(
                self.problem_cfg,
                var_lb=config['problem']['var_lb'],
                var_ub=config['problem']['var_ub'],
                obj_lb=config['problem']['obj_lb'],
                obj_ub=config['problem']['obj_ub'],
            )
        
        if self.config != old_config:
            self.save_config(self.config)
            self.worker_agent.set_config(self.config, self.config_id)
            self.controller['viz_space'].set_config(self.config, self.problem_cfg)
            self.controller['viz_stats'].set_config(self.config, self.problem_cfg)

        return True

    def save_config(self, config):
        '''
        Save configurations to file
        '''
        # convert all numpy array to list
        def convert_config(config):
            for key, val in config.items():
                if type(val) == np.ndarray:
                    config[key] = val.tolist()
                elif type(val) == dict:
                    convert_config(config[key])

        config = config.copy()
        convert_config(config)

        self.config_id += 1
        with open(os.path.join(self.result_dir, 'config', f'config_{self.config_id}.yml'), 'w') as fp:
            yaml.dump(config, fp, default_flow_style=False, sort_keys=False)

    def get_timestamp(self):
        return self.timestamp

    def set_timestamp(self):
        self.timestamp = time()

    def set_result_dir(self, result_dir):
        self.result_dir = result_dir

    def create_result_dir(self, window):
        # check if result_dir folder is not empty
        if os.path.exists(self.result_dir) and os.listdir(self.result_dir) != []:
            overwrite = tk.messagebox.askquestion('Error', f'Result folder {self.result_dir} is not empty, do you want to overwrite? If not, please change another folder for saving results by clicking: File -> Save in...', parent=window)
            if overwrite == 'no':
                return False
            else:
                shutil.rmtree(self.result_dir)
        os.makedirs(self.result_dir, exist_ok=True)
        config_dir = os.path.join(self.result_dir, 'config')
        os.makedirs(config_dir)
        return True

    def refresh(self):
        '''
        Refresh current GUI status and redraw if data has changed
        '''
        self.worker_agent.refresh()
        
        # can optimize and load config when worker agent is empty
        if self.worker_agent.empty():
            self.controller['panel_control'].view.widget['mode'].enable()
            self.controller['panel_control'].view.widget['optimize'].enable()
            self.controller['panel_control'].view.widget['stop'].disable()
            if self.view.menu_config.entrycget(0, 'state') == tk.DISABLED:
                self.view.menu_config.entryconfig(0, state=tk.NORMAL)
            if self.view.menu_config.entrycget(2, 'state') == tk.DISABLED:
                self.view.menu_config.entryconfig(2, state=tk.NORMAL)

        # post-process worker logs
        log_list = []
        status, rowids = [], []
        evaluated = False
        for log in self.worker_agent.read_log():
            log = log.split('/') 
            log_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S\n') + log[0] + '\n'
            log_list.append(log_text)

        # log display
        self.controller['panel_log'].log(log_list)

        # update visualization
        opt_done, eval_done = self.data_agent.check_opt_done(), self.data_agent.check_eval_done()

        if eval_done:
            self.controller['viz_space'].redraw_performance_space(reset_scaler=True)
            self.controller['viz_stats'].redraw()
        
        self.controller['viz_database'].update_data(opt_done, eval_done)

        # check stopping criterion
        self.check_stop_criterion()
        
        # trigger another refresh
        self.after_handle = self.root.after(self.refresh_rate, self.refresh)

    def check_stop_criterion(self):
        '''
        Check if stopping criterion is met
        '''
        stop = False
        stop_criterion = self.controller['panel_control'].stop_criterion
        n_valid_sample = self.data_agent.get_n_valid_sample()

        for key, val in stop_criterion.items():
            if key == 'time': # optimization & evaluation time
                if time() - self.timestamp >= val:
                    stop = True
                    self.timestamp = None
            elif key == 'n_sample': # number of samples
                if n_valid_sample >= val:
                    stop = True
            elif key == 'hv_value': # hypervolume value
                if self.controller['viz'].view.line_hv.get_ydata()[-1] >= val:
                    stop = True
            elif key == 'hv_conv': # hypervolume convergence
                hv_history = self.controller['viz'].view.line_hv.get_ydata()
                checkpoint = np.clip(int(n_valid_sample * val / 100.0), 1, n_valid_sample - 1)
                if hv_history[-checkpoint] == hv_history[-1]:
                    stop = True
            else:
                raise NotImplementedError
        
        if stop:
            stop_criterion.clear()
            self.worker_agent.stop_worker()
            self.controller['panel_log'].log('stopping criterion is met')
        
    def _quit(self):
        '''
        Quit handling
        '''
        self.data_agent.quit()
        self.worker_agent.quit()
        self.database.quit()

        if self.after_handle is not None:
            self.root.after_cancel(self.after_handle)
        self.root.quit()
        self.root.destroy()

    def run(self):
        self.root_login.mainloop()