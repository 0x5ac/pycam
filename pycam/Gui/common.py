import OpenGL.GL as GL
import OpenGL.GLUT as GLUT
# "ode" is imported later, if required
#import ode_objects
import random
import gtk


MODEL_TRANSFORMATIONS = {
    "normal": ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)),
    "x": ((1, 0, 0, 0), (0, 0, 1, 0), (0, -1, 0, 0)),
    "y": ((0, 0, -1, 0), (0, 1, 0, 0), (1, 0, 0, 0)),
    "z": ((0, 1, 0, 0), (-1, 0, 0, 0), (0, 0, 1, 0)),
    "xy": ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, -1, 0)),
    "xz": ((1, 0, 0, 0), (0, -1, 0, 0), (0, 0, 1, 0)),
    "yz": ((-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0)),
    "x_swap_y": ((0, 1, 0, 0), (1, 0, 0, 0), (0, 0, 1, 0)),
    "x_swap_z": ((0, 0, 1, 0), (0, 1, 0, 0), (1, 0, 0, 0)),
    "y_swap_z": ((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0)),
}

COLORS = {
    "model": (0.5, 0.5, 1.0),
    "bounding": (0.3, 0.3, 0.3),
    "cutter": (1.0, 0.2, 0.2),
    "toolpath_way": (1.0, 0.5, 0.5),
    "toolpath_back": (0.5, 1.0, 0.5),
}

def keep_gl_mode(func):
    def wrapper(*args, **kwargs):
        prev_mode = GL.glGetIntegerv(GL.GL_MATRIX_MODE)
        func(*args, **kwargs)
        GL.glMatrixMode(prev_mode)
    return wrapper

def keep_matrix(func):
    def wrapper(*args, **kwargs):
        pushed_matrix_mode = GL.glGetIntegerv(GL.GL_MATRIX_MODE)
        GL.glPushMatrix()
        func(*args, **kwargs)
        final_matrix_mode = GL.glGetIntegerv(GL.GL_MATRIX_MODE)
        GL.glMatrixMode(pushed_matrix_mode)
        GL.glPopMatrix()
        GL.glMatrixMode(final_matrix_mode)
    return wrapper

@keep_matrix
def draw_string(x, y, z, p, s, scale=.01):
    GL.glPushMatrix()
    GL.glTranslatef(x, y, z)
    if p == 'xy':
        pass
    elif p == 'yz':
        GL.glRotatef(90, 0, 1, 0)
        GL.glRotatef(90, 0, 0, 1)
    elif p == 'xz':
        GL.glRotatef(90, 0, 1, 0)
        GL.glRotatef(90, 0, 0, 1)
        GL.glRotatef(-90, 0, 1, 0)
    GL.glScalef(scale, scale, scale)
    for c in str(s):
        GLUT.glutStrokeCharacter(GLUT.GLUT_STROKE_ROMAN, ord(c))
    GL.glPopMatrix()

@keep_gl_mode
@keep_matrix
def draw_axes(settings):
    GL.glMatrixMode(GL.GL_MODELVIEW)
    GL.glLoadIdentity()
    #GL.glTranslatef(0, 0, -2)
    if settings.get("unit") == "mm":
        size = 100
    else:
        size = 5
    GL.glBegin(GL.GL_LINES)
    GL.glColor3f(1, 0, 0)
    GL.glVertex3f(0, 0, 0)
    GL.glVertex3f(size, 0, 0)
    GL.glEnd()
    draw_string(size, 0, 0, 'xy', "X")
    GL.glBegin(GL.GL_LINES)
    GL.glColor3f(0, 1, 0)
    GL.glVertex3f(0, 0, 0)
    GL.glVertex3f(0, size, 0)
    GL.glEnd()
    draw_string(0, size, 0, 'yz', "Y")
    GL.glBegin(GL.GL_LINES)
    GL.glColor3f(0, 0, 1)
    GL.glVertex3f(0, 0, 0)
    GL.glVertex3f(0, 0, size)
    GL.glEnd()
    draw_string(0, 0, size, 'xz', "Z")

@keep_matrix
def draw_bounding_box(minx, miny, minz, maxx, maxy, maxz):
    color = COLORS["bounding"]
    p1 = [minx, miny, minz]
    p2 = [minx, maxy, minz]
    p3 = [maxx, maxy, minz]
    p4 = [maxx, miny, minz]
    p5 = [minx, miny, maxz]
    p6 = [minx, maxy, maxz]
    p7 = [maxx, maxy, maxz]
    p8 = [maxx, miny, maxz]
    # lower rectangle
    GL.glBegin(GL.GL_LINES)
    GL.glColor3f(*color)
    # all combinations of neighbouring corners
    for corner_pair in [(p1, p2), (p1, p5), (p1, p4), (p2, p3),
                (p2, p6), (p3, p4), (p3, p7), (p4, p8), (p5, p6),
                (p6, p7), (p7, p8), (p8, p5)]:
        GL.glVertex3f(*(corner_pair[0]))
        GL.glVertex3f(*(corner_pair[1]))
    GL.glEnd()

@keep_gl_mode
@keep_matrix
def draw_cutter(cutter):
    if not cutter is None:
        GL.glColor3f(*COLORS["cutter"])
        cutter.to_OpenGL()

@keep_gl_mode
@keep_matrix
def draw_complete_model_view(settings):
    GL.glMatrixMode(GL.GL_MODELVIEW)
    GL.glLoadIdentity()
    # axes
    if settings.get("show_axes"):
        draw_axes(settings)
    # stock model
    if settings.get("show_bounding_box"):
        draw_bounding_box(float(settings.get("minx")), float(settings.get("miny")),
                float(settings.get("minz")), float(settings.get("maxx")),
                float(settings.get("maxy")), float(settings.get("maxz")))
    # draw the model
    if settings.get("show_model"):
        GL.glColor3f(*COLORS["model"])
        settings.get("model").to_OpenGL()
    # draw the toolpath
    if settings.get("show_toolpath"):
        for toolpath_obj in settings.get("toolpath"):
            if toolpath_obj.visible:
                draw_toolpath(toolpath_obj.get_path())
    # draw the drill
    if settings.get("show_drill_progress"):
        draw_cutter(settings.get("cutter"))

@keep_gl_mode
@keep_matrix
def draw_toolpath(toolpath):
    GL.glMatrixMode(GL.GL_MODELVIEW)
    GL.glLoadIdentity()
    if toolpath:
        last = None
        for path in toolpath:
            if last:
                GL.glColor3f(*COLORS["toolpath_back"])
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(last.x, last.y, last.z)
                last = path.points[0]
                GL.glVertex3f(last.x, last.y, last.z)
                GL.glEnd()
            GL.glColor3f(*COLORS["toolpath_way"])
            GL.glBegin(GL.GL_LINE_STRIP)
            for point in path.points:
                GL.glVertex3f(point.x, point.y, point.z)
            GL.glEnd()
            last = path.points[-1]

@keep_gl_mode
def rotate_view(scale, rotation=None):
    GL.glMatrixMode(GL.GL_PROJECTION)
    GL.glLoadIdentity()
    GL.glScalef(scale, scale, scale)
    if rotation:
        for one_rot in rotation:
            GL.glRotatef(*one_rot)

def transform_model(model, direction="normal"):
    model.transform(MODEL_TRANSFORMATIONS[direction])

def shift_model(model, shift_x, shift_y, shift_z):
    matrix = ((1, 0, 0, shift_x), (0, 1, 0, shift_y), (0, 0, 1, shift_z))
    model.transform(matrix)
    
def scale_model(model, scale):
    matrix = ((scale, 0, 0, 0), (0, scale, 0, 0), (0, 0, scale, 0))
    model.transform(matrix)

def generate_physics(settings, cutter, physics=None):
    import ode_objects
    if physics is None:
        physics = ode_objects.PhysicalWorld()
    physics.reset()
    physics.add_mesh((0, 0, 0), settings.get("model").triangles())
    shape_info = cutter.get_shape("ODE", additional_distance=settings.get("material_allowance"))
    physics.set_drill(shape_info[0], (0.0, 0.0, 0.0))
    return physics

def is_ode_available():
    try:
        import ode
        return True
    except ImportError:
        return False


class ToolPathList(list):

    def add_toolpath(self, toolpath, name, cutter, *args):
        drill_id = self._get_drill_id(cutter)
        self.append(ToolPathInfo(toolpath, name, drill_id, cutter, *args))

    def _get_drill_id(self, cutter):
        used_ids = []
        # check if a drill with the same dimensions was used before
        for tp in self:
            if tp.drill == cutter:
                return tp.drill_id
            else:
                used_ids.append(tp.drill_id)
        # find the smallest unused drill id
        index = 1
        while index in used_ids:
            index += 1
        return index


class ToolPathInfo:

    def __init__(self, toolpath, name, drill_id, cutter, speed, feedrate,
            material_allowance, safety_height, unit, start_x, start_y, start_z):
        self.toolpath = toolpath
        self.name = name
        self.visible = True
        self.drill_id = drill_id
        self.drill = cutter
        self.drill_size = cutter.radius
        self.speed = speed
        self.feedrate = feedrate
        self.material_allowance = material_allowance
        self.safety_height = safety_height
        self.unit = unit
        self.start_x = start_x
        self.start_y = start_y
        self.start_z = start_z
        self.color = None
        # generate random color
        self.set_color()

    def get_path(self):
        return self.toolpath

    def set_color(self, color=None):
        color_max = 65535
        if color is None:
            self.color = gtk.gdk.Color(random.randint(0, color_max),
                    random.randint(0, color_max), random.randint(0, color_max))
        else:
            self.color = color
