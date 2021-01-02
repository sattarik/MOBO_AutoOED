import tkinter as tk
from system.gui.widgets.factory import create_widget
from system.scientist.gui.map import config_map


class AutoSetScriptView:

    def __init__(self, root_view):
        self.root_view = root_view

        self.window = tk.Toplevel(master=self.root_view.root)
        self.window.title('Set Evaluation Script')
        self.window.resizable(False, False)

        self.widget = {}

        frame_script = create_widget('frame', master=self.window, row=0, column=0)
        self.widget['browse_p_eval'], self.widget['disp_p_eval'] = create_widget('labeled_button_entry',
            master=frame_script, row=0, column=0, label_text=config_map['problem']['performance_eval'], button_text='Browse', width=30, required=True)
        self.widget['browse_c_eval'], self.widget['disp_c_eval'] = create_widget('labeled_button_entry',
            master=frame_script, row=1, column=0, label_text=config_map['problem']['constraint_eval'], button_text='Browse', width=30)

        frame_action = tk.Frame(master=self.window)
        frame_action.grid(row=1, column=0)
        self.widget['save'] = create_widget('button', master=frame_action, row=0, column=0, text='Save')
        self.widget['cancel'] = create_widget('button', master=frame_action, row=0, column=1, text='Cancel')