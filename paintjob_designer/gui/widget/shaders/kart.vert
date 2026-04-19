#version 330 core
layout (location = 0) in vec3 in_pos;
layout (location = 1) in vec2 in_uv;
layout (location = 2) in vec3 in_normal;
layout (location = 3) in float in_highlight;
layout (location = 4) in vec3 in_vcolor;

uniform mat4 u_mvp;

out vec2 v_uv;
out vec3 v_normal;
out float v_highlight;
out vec3 v_vcolor;

void main() {
    gl_Position = u_mvp * vec4(in_pos, 1.0);
    v_uv = in_uv;
    v_normal = in_normal;
    v_highlight = in_highlight;
    v_vcolor = in_vcolor;
}
