#version 330 core
layout (location = 0) in vec3 in_pos;
layout (location = 1) in vec2 in_uv;
layout (location = 2) in vec3 in_normal;
layout (location = 3) in float in_highlight;

uniform mat4 u_mvp;

out vec2 v_uv;
out vec3 v_normal;
out float v_highlight;

void main() {
    gl_Position = u_mvp * vec4(in_pos, 1.0);
    v_uv = in_uv;
    v_normal = in_normal;
    v_highlight = in_highlight;
}
