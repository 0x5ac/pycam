# -*- coding: utf-8 -*-
"""
$Id$

Copyright 2011 Lars Kruse <devel@sumpfralle.de>

This file is part of PyCAM.

PyCAM is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PyCAM is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PyCAM.  If not, see <http://www.gnu.org/licenses/>.
"""


import pycam.Plugins


class ModelScaling(pycam.Plugins.PluginBase):

    UI_FILE = "model_scaling.ui"

    def setup(self):
        if self.gui:
            scale_box = self.gui.get_object("ModelScaleBox")
            scale_box.unparent()
            self.core.register_ui("model_handling", "Scale", scale_box, -5)
            self.core.register_event("model-change-after",
                    self._update_scale_dimensions)
            update_model = lambda widget=None: self.core.emit_event(
                    "model-change-after")
            scale_percent = self.gui.get_object("ScalePercent")
            scale_button = self.gui.get_object("ScaleModelButton")
            scale_percent.set_value(100)
            scale_percent.connect("focus-in-event",
                    lambda widget, data: scale_button.grab_default())
            scale_percent.connect("focus-out-event", lambda widget, data: \
                    scale_box.get_toplevel().set_default(None))
            scale_button.connect("clicked", self._scale_model)
            # scale model to an axis dimension
            self.gui.get_object("ScaleDimensionAxis").connect("changed",
                    update_model)
            scale_dimension_button = self.gui.get_object("ScaleAllAxesButton")
            scale_dimension_control = self.gui.get_object(
                    "ScaleDimensionControl")
            scale_dimension_control.connect("focus-in-event",
                    lambda widget, data: scale_dimension_button.grab_default())
            scale_dimension_control.connect("focus-out-event",
                    lambda widget, data: \
                            scale_box.get_toplevel().set_default(None))
            scale_dimension_button.connect("clicked",
                    self._scale_model_axis_fit, True)
            self.gui.get_object("ScaleSelectedAxisButton").connect("clicked",
                    self._scale_model_axis_fit, False)
            self.gui.get_object("ScaleInchMM").connect("clicked",
                    self._scale_model, 100 * 25.4)
            self.gui.get_object("ScaleMMInch").connect("clicked",
                    self._scale_model, 100 / 25.4)
        return True

    def teardown(self):
        if self.gui:
            self.core.unregister_ui("model_handling",
                    self.gui.get_object("ModelScaleBox"))

    def _update_scale_dimensions(self):
        model = self.core.get("model")
        if not model:
            return
        # scale controls
        axis_control = self.gui.get_object("ScaleDimensionAxis")
        scale_button = self.gui.get_object("ScaleSelectedAxisButton")
        scale_value = self.gui.get_object("ScaleDimensionControl")
        index = axis_control.get_active()
        dims = (model.maxx - model.minx, model.maxy - model.miny,
                model.maxz - model.minz)
        value = dims[index]
        non_zero_dimensions = [i for i, dim in enumerate(dims) if dim > 0]
        enable_controls = index in non_zero_dimensions
        scale_button.set_sensitive(enable_controls)
        scale_value.set_sensitive(enable_controls)
        scale_value.set_value(value)

    def _scale_model(self, widget=None, percent=None):
        model = self.core.get("model")
        if not model:
            return
        if percent is None:
            percent = self.gui.get_object("ScalePercent").get_value()
        factor = percent / 100.0
        if (factor <= 0) or (factor == 1):
            return
        self.core.emit_event("model-change-before")
        self.core.get("update_progress")("Scaling model")
        self.core.get("disable_progress_cancel_button")()
        model.scale(factor, callback=self.core.get("update_progress"))
        self.core.emit_event("model-change-after")

    def _scale_model_axis_fit(self, widget=None, proportionally=False):
        model = self.core.get("model")
        if not model:
            return
        value = self.gui.get_object("ScaleDimensionValue").get_value()
        index = self.gui.get_object("ScaleDimensionAxis").get_active()
        axes = "xyz"
        axis_suffix = axes[index]
        factor = value / (getattr(model, "max" + axis_suffix) - \
                getattr(model, "min" + axis_suffix))
        self.core.emit_event("model-change-before")
        self.core.get("update_progress")("Scaling model")
        self.core.get("disable_progress_cancel_button")()
        if proportionally:
            model.scale(factor, callback=self.core.get("update_progress"))
        else:
            factor_x, factor_y, factor_z = (1, 1, 1)
            if index == 0:
                factor_x = factor
            elif index == 1:
                factor_y = factor
            elif index == 2:
                factor_z = factor
            else:
                return
            model.scale(factor_x, factor_y, factor_z,
                    callback=self.core.get("update_progress"))
        # move the model to its previous center
        self.core.emit_event("model-change-after")
