# -*- coding: utf-8 -*-
"""
$Id$

Copyright 2010 Lars Kruse <devel@sumpfralle.de>

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

from pycam.Geometry.Point import Point, Vector
from pycam.Geometry.Line import Line
from pycam.Geometry.Plane import Plane
from pycam.PathGenerators import get_free_paths_ode, get_free_paths_triangles
from pycam.Geometry.utils import epsilon, ceil, sqrt
from pycam.Geometry import get_bisector, get_angle_pi
from pycam.Utils import ProgressCounter
import random
import math


class WaterlineTriangles:

    def __init__(self):
        self.waterlines = []
        self.shifted_lines = []

    def __str__(self):
        lines = []
        for index, t in enumerate(self.triangles):
            lines.append("%d - %s" % (index, t))
            if not self.left[index]:
                left_index = None
            else:
                left_index = []
                for left in self.left[index]:
                    left_index.append(self.triangles.index(left))
            if not self.right[index]:
                right_index = None
            else:
                right_index = []
                for right in self.right[index]:
                    right_index.append(self.triangles.index(right))
            lines.append("\t%s / %s" % (left_index, right_index))
            lines.append("\t%s" % str(self.waterlines[index]))
            lines.append("\t%s" % str(self.shifted_lines[index]))
        return "\n".join(lines)

    def add(self, waterline, shifted_line):
        if waterline in self.waterlines:
            # ignore this triangle
            return
        self.waterlines.append(waterline)
        self.shifted_lines.append(shifted_line)

    def _get_groups(self):
        if len(self.waterlines) == 0:
            return []
        queue = range(len(self.waterlines))
        current_group = [0]
        queue.pop(0)
        groups = [current_group]
        while queue:
            for index in queue:
                if self.waterlines[index].p2 == self.waterlines[current_group[0]].p1:
                    current_group.insert(0, index)
                    queue.remove(index)
                    break
            else:
                # no new members added to this group - start a new one
                current_group = [queue[0]]
                queue.pop(0)
                groups.append(current_group)
        return groups

    def extend_shifted_lines(self):
        # TODO: improve the code below to handle "holes" properly (neighbours that disappear due to a negative collision distance - use the example "SampleScene.stl" as a reference)
        def get_right_neighbour(group, ref):
            group_len = len(group)
            # limit the search for a neighbour for non-closed groups
            if self.waterlines[group[0]].p1 == self.waterlines[group[-1]].p2:
                index_range = range(ref + 1, ref + group_len)
            else:
                index_range = range(ref + 1, group_len)
            for index in index_range:
                line_id = group[index % group_len]
                if not self.shifted_lines[line_id] is None:
                    return line_id
            else:
                return None
        groups = self._get_groups()
        for group in groups:
            index = 0
            while index < len(group):
                current = group[index]
                current_shifted = self.shifted_lines[current]
                if current_shifted is None:
                    index += 1
                    continue
                neighbour = get_right_neighbour(group, index)
                if neighbour is None:
                    # no right neighbour available
                    break
                neighbour_shifted = self.shifted_lines[neighbour]
                if current_shifted.p2 == neighbour_shifted.p1:
                    index += 1
                    continue
                cp, dist = current_shifted.get_intersection(neighbour_shifted, infinite_lines=True)
                cp2, dist2 = neighbour_shifted.get_intersection(current_shifted, infinite_lines=True)
                if dist < epsilon:
                    self.shifted_lines[current] = None
                    index -= 1
                elif dist2 > 1 - epsilon:
                    self.shifted_lines[neighbour] = None
                else:
                    self.shifted_lines[current] = Line(current_shifted.p1, cp)
                    self.shifted_lines[neighbour] = Line(cp, neighbour_shifted.p2)
                    index += 1

    def get_shifted_lines(self):
        result = []
        groups = self._get_groups()
        for group in groups:
            for index in group:
                if not self.shifted_lines[index] is None:
                    result.append(self.shifted_lines[index])
        return result


class Waterline:

    def __init__(self, cutter, model, path_processor, physics=None):
        self.cutter = cutter
        self.model = model
        self.pa = path_processor
        self._up_vector = Vector(0, 0, 1)
        self.physics = physics
        if self.physics:
            accuracy = 20
            max_depth = 16
            model_dim = max(abs(self.model.maxx - self.model.minx),
                    abs(self.model.maxy - self.model.miny))
            depth = math.log(accuracy * model_dim / self.cutter.radius) / math.log(2)
            self._physics_maxdepth = min(max_depth, max(ceil(depth_x), 4))

    def _get_free_paths(self, p1, p2):
        if self.physics:
            return get_free_paths_ode(self.physics, p1, p2,
                    depth=self._physics_maxdepth)
        else:
            return get_free_paths_triangles(self.model, self.cutter, p1, p2)

    def GenerateToolPath(self, minx, maxx, miny, maxy, minz, maxz, dz,
            draw_callback=None):
        # calculate the number of steps
        # Sometimes there is a floating point accuracy issue: make sure
        # that only one layer is drawn, if maxz and minz are almost the same.
        if abs(maxz - minz) < epsilon:
            diff_z = 0
        else:
            diff_z = abs(maxz - minz)
        num_of_layers = 1 + ceil(diff_z / dz)
        z_step = diff_z / max(1, (num_of_layers - 1))

        num_of_triangles = len(self.model.triangles(minx=minx, miny=miny, maxx=maxx, maxy=maxy))
        progress_counter = ProgressCounter(2 * num_of_layers * num_of_triangles,
                draw_callback)

        current_layer = 0

        z_steps = [(maxz - i * z_step) for i in range(num_of_layers)]

        # collision handling function
        for z in z_steps:
            # update the progress bar and check, if we should cancel the process
            if draw_callback and draw_callback(text="PushCutter: processing" \
                        + " layer %d/%d" % (current_layer + 1, num_of_layers)):
                # cancel immediately
                break
            self.pa.new_direction(0)
            self.GenerateToolPathSlice(minx, maxx, miny, maxy, z,
                    draw_callback, progress_counter)
            self.pa.end_direction()
            self.pa.finish()
            current_layer += 1
        return self.pa.paths

    def GenerateToolPathSlice(self, minx, maxx, miny, maxy, z,
            draw_callback=None, progress_counter=None):
        shifted_lines = self.get_potential_contour_lines(minx, maxx, miny, maxy,
                z, progress_counter=progress_counter)
        last_position = None
        self.pa.new_scanline()
        for line in shifted_lines:
            points = self._get_free_paths(line.p1, line.p2)
            if points:
                if (not last_position is None) and (len(points) > 0) \
                        and (last_position != points[0]):
                    self.pa.end_scanline()
                    self.pa.new_scanline()
                for p in points:
                    self.pa.append(p)
                self.cutter.moveto(p)
                if draw_callback:
                    draw_callback(tool_position=p, toolpath=self.pa.paths)
                last_position = p
            # update the progress counter
            if not progress_counter is None:
                if progress_counter.increment():
                    # quit requested
                    break
        # the progress counter jumps up by the number of non directly processed triangles
        if not progress_counter is None:
            progress_counter.increment(len(self.model.triangles()) - len(shifted_lines))
        self.pa.end_scanline()
        return self.pa.paths

    def get_potential_contour_lines(self, minx, maxx, miny, maxy, z,
            progress_counter=None):
        plane = Plane(Point(0, 0, z), self._up_vector)
        lines = []
        waterline_triangles = WaterlineTriangles()
        projected_waterlines = []
        for triangle in self.model.triangles(minx=minx, miny=miny, maxx=maxx, maxy=maxy):
            if not progress_counter is None:
                if progress_counter.increment():
                    # quit requested
                    break
            # ignore triangles below the z level
            if triangle.maxz < z:
                continue
            # ignore triangles pointing upwards or downwards
            if triangle.normal.cross(self._up_vector).norm == 0:
                continue
            edge_collisions = self.get_collision_waterline_of_triangle(triangle, z)
            if not edge_collisions:
                continue
            for cutter_location, edge in edge_collisions:
                shifted_edge = self.get_shifted_waterline(edge, cutter_location)
                if shifted_edge is None:
                    continue
                waterline_triangles.add(edge, shifted_edge)
        waterline_triangles.extend_shifted_lines()
        result = []
        for line in waterline_triangles.get_shifted_lines():
            cropped_line = line.get_cropped_line(minx, maxx, miny, maxy, z, z)
            if not cropped_line is None:
                result.append(cropped_line)
        return result

    def get_max_length(self):
        if not hasattr(self, "_max_length_cache"):
            # update the cache
            x_dim = abs(self.model.maxx - self.model.minx)
            y_dim = abs(self.model.maxy - self.model.miny)
            z_dim = abs(self.model.maxz - self.model.minz)
            self._max_length_cache = sqrt(x_dim ** 2 + y_dim ** 2 + z_dim ** 2)
        return self._max_length_cache

    def get_collision_waterline_of_triangle(self, triangle, z):
        # TODO: there are problems with "material allowance > 0"
        plane = Plane(Point(0, 0, z), self._up_vector)
        if triangle.minz > z:
            # the triangle is completely above z
            # try all edges
            proj_points = []
            for p in triangle.get_points():
                proj_p = plane.get_point_projection(p)
                if not proj_p in proj_points:
                    proj_points.append(proj_p)
            if len(proj_points) == 3:
                edges = []
                for index in range(3):
                    edge = Line(proj_points[index - 1], proj_points[index])
                    # the edge should be clockwise around the model
                    if edge.dir.cross(triangle.normal).dot(self._up_vector) < 0:
                        edge = Line(edge.p2, edge.p1)
                    edges.append((edge, proj_points[index - 2]))
                outer_edges = []
                for edge, other_point in edges:
                    # pick only edges, where the other point is on the right side
                    if other_point.sub(edge.p1).cross(edge.dir).dot(self._up_vector) > 0:
                        outer_edges.append(edge)
                if len(outer_edges) == 0:
                    # the points seem to be an one line
                    # pick the longest edge
                    long_edge = edges[0][0]
                    for edge, other_point in edges[1:]:
                        if edge.len > long_edge.len:
                            long_edge = edge
                    outer_edges = long_edge
            else:
                edge = Line(proj_points[0], proj_points[1])
                if edge.dir.cross(triangle.normal).dot(self._up_vector) < 0:
                    edge = Line(edge.p2, edge.p1)
                outer_edges = [edge]
        else:
            points_above = [plane.get_point_projection(p) for p in triangle.get_points() if p.z > z]
            waterline = plane.intersect_triangle(triangle)
            if waterline is None:
                if len(points_above) == 2:
                    edge = Line(points_above[0], points_above[1])
                    if edge.dir.cross(triangle.normal).dot(self._up_vector) < 0:
                        outer_edges = [Line(edge.p2, edge.p1)]
                    else:
                        outer_edges = [edge]
                else:
                    outer_edges = []
            else:
                # remove points that are not part of the waterline
                points_above = [p for p in points_above
                        if (p != waterline.p1) and (p != waterline.p2)]
                potential_edges = []
                if len(points_above) == 0:
                    outer_edges = [waterline]
                elif len(points_above) == 1:
                    other_point = points_above[0]
                    dot = other_point.sub(waterline.p1).cross(waterline.dir).dot(self._up_vector)
                    if dot > 0:
                        outer_edges = [waterline]
                    elif dot < 0:
                        edges = []
                        edges.append(Line(waterline.p1, other_point))
                        edges.append(Line(waterline.p2, other_point))
                        outer_edges = []
                        for edge in edges:
                            if edge.dir.cross(triangle.normal).dot(self._up_vector) < 0:
                                outer_edges.append(Line(edge.p2, edge.p1))
                            else:
                                outer_edges.append(edge)
                    else:
                        # the three points are on one line
                        edges = []
                        edges.append(waterline)
                        edges.append(Line(waterline.p1, other_point))
                        edges.append(Line(waterline.p2, other_point))
                        edges.sort(key=lambda x: x.len)
                        outer_edges = [edges[-1]]
                else:
                    # two points above
                    other_point = points_above[0]
                    dot = other_point.sub(waterline.p1).cross(waterline.dir).dot(self._up_vector)
                    if dot > 0:
                        # the other two points are on the right side
                        outer_edges = [waterline]
                    elif dot < 0:
                        edge = Line(points_above[0], points_above[1])
                        if edge.dir.cross(triangle.normal).dot(self._up_vector) < 0:
                            outer_edges = [Line(edge.p2, edge.p1)]
                        else:
                            outer_edges = [edge]
                    else:
                        edges = []
                        # pick the longest combination of two of these points
                        points = [waterline.p1, waterline.p2] + points_above
                        for p1 in points:
                            for p2 in points:
                                if not p1 is p2:
                                    edges.append(Line(p1, p2))
                        edges.sort(key=lambda x: x.len)
                        edge = edges[-1]
                        if edge.dir.cross(triangle.normal).dot(self._up_vector) < 0:
                            outer_edges = [Line(edge.p2, edge.p1)]
                        else:
                            outer_edges = [edge]
        result = []
        for edge in outer_edges:
            start = edge.p1.add(edge.p2).div(2)
            direction = self._up_vector.cross(edge.dir).normalized()
            if direction is None:
                continue
            direction = direction.mul(self.get_max_length())
            # We need to use the triangle collision algorithm here - because we
            # need the point of collision in the triangle.
            collisions = get_free_paths_triangles(self.model, self.cutter, start,
                    start.add(direction), return_triangles=True)
            for index, coll in enumerate(collisions):
                if (index % 2 == 0) and (not coll[1] is None) \
                        and (not coll[2] is None) \
                        and (coll[0].sub(start).dot(direction) > 0):
                    cl, hit_t, cp = coll
                    break
            else:
                raise ValueError("Failed to detect any collision: " \
                        + "%s / %s -> %s" % (edge, start, direction))
            proj_cp = plane.get_point_projection(cp)
            if edge.is_point_inside(proj_cp):
                result.append((cl, edge))
        return result

    def get_shifted_waterline(self, waterline, cutter_location):
        # Project the waterline and the cutter location down to the slice plane.
        # This is necessary for calculating the horizontal distance between the
        # cutter and the triangle waterline.
        plane = Plane(cutter_location, self._up_vector)
        wl_proj = plane.get_line_projection(waterline)
        if wl_proj.len < epsilon:
            return None
        offset = wl_proj.dist_to_point(cutter_location)
        if offset < epsilon:
            return wl_proj
        # shift both ends of the waterline towards the cutter location
        shift = cutter_location.sub(wl_proj.closest_point(cutter_location))
        shifted_waterline = Line(wl_proj.p1.add(shift), wl_proj.p2.add(shift))
        return shifted_waterline

