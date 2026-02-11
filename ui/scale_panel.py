def create_scale_settings(self):
        self.box_scale_settings = QWidget()
        # self.box_scale_settings.setStyleSheet("QWidget""{""background : white;""}")
        layout = QGridLayout()

        # scale factor
        label_scale_factor = QLabel('scale factor', self)

        box_scale_factor = QWidget()
        layout_scale_factor = QGridLayout()
        label_1e = QLabel('1E', self)
        spin_box_scale_factor = self.spin_box(-20, 20, self.scale_factor)
        spin_box_scale_factor.valueChanged[int].connect(self.set_scale_factor)
        layout_scale_factor.addWidget(label_1e, 0, 0, 1, 1)
        layout_scale_factor.addWidget(spin_box_scale_factor, 0, 1, 1, 2)
        box_scale_factor.setLayout(layout_scale_factor)

        # maximum value
        label_max_value = QLabel('maximum value', self)
        spin_box_max_value = self.spin_box(-100, 100, self.max_value)
        spin_box_max_value.valueChanged[int].connect(self.set_max_value)

        # minimum value
        label_min_value = QLabel('minimum value', self)
        spin_box_min_value = self.spin_box(-100, 100, self.min_value)
        spin_box_min_value.valueChanged[int].connect(self.set_min_value)

        # scale step
        # label_scale_step = QtWidgets.QLabel('scale step', self)
        # spin_box_scale_step = self.spin_box(0, 100, 2)
        # spin_box_scale_step.valueChanged[int].connect(self.set_scale_step)

        # scale offset
        label_scale_offset = QLabel('scale offset', self)
        spin_box_scale_offset = self.spin_box(-100, 100, self.scale_offset)
        spin_box_scale_offset.valueChanged[int].connect(self.set_scale_offset)

        # time range
        label_time_range_EMG = QLabel('time range EMG', self)
        box_time_range_EMG = self.spin_box_with_unit(unit='c', min=0, max=20, value=int(self.time_range_emg // 1000), function=self.set_time_range_emg)
        
        label_time_range_CLF = QLabel('time range CLF', self)
        box_time_range_CLF = self.spin_box_with_unit(unit='c', min=0, max=20, value=int(self.time_range_clf // 1000), function=self.set_time_range_clf)

        row = 0
        layout.addWidget(label_scale_factor, row, 0)
        layout.addWidget(box_scale_factor, row, 1)
        layout.addWidget(label_scale_offset, row, 2)
        layout.addWidget(spin_box_scale_offset, row, 3)
        row += 1
        layout.addWidget(label_max_value, row, 0)
        layout.addWidget(spin_box_max_value, row, 1)
        layout.addWidget(label_min_value, row, 2)
        layout.addWidget(spin_box_min_value, row, 3)
        row += 1
        layout.addWidget(label_time_range_CLF, row, 0)
        layout.addWidget(box_time_range_CLF, row, 1)
        layout.addWidget(label_time_range_EMG, row, 2)
        layout.addWidget(box_time_range_EMG, row, 3)
        # row += 1
        # layout.addWidget(label_scale_step, row, 0)
        # layout.addWidget(spin_box_scale_step, row, 1)
        row += 1
        

        self.box_scale_settings.setLayout(layout)
    

    