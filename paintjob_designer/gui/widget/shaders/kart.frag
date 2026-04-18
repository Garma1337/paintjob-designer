#version 330 core

// Half-Lambert wrap so the dark side isn't pitch-black; an ambient floor keeps
// triangles facing away from the light still legible.

in vec2 v_uv;
in vec3 v_normal;
in float v_highlight;

uniform sampler2D u_atlas;
uniform int u_has_focus;

out vec4 out_color;

const vec3 LIGHT_DIR = normalize(vec3(0.35, 0.85, 0.4));
const float AMBIENT = 0.45;
const float DIMMED_FACTOR = 0.22;

vec3 apply_shade(vec3 base) {
    vec3 n = normalize(v_normal);
    float lambert = max(dot(n, LIGHT_DIR), 0.0);
    float wrap = 0.5 + 0.5 * lambert;
    float factor = AMBIENT + (1.0 - AMBIENT) * wrap;
    return base * factor;
}

// Untextured triangles carry the sentinel UV (-1, -1) from AtlasUvMapper.
// Render them as a flat mid-gray (still shaded) instead of sampling the atlas.
void main() {
    vec3 base;
    float alpha;

    if (v_uv.x < 0.0) {
        base = vec3(0.55);
        alpha = 1.0;
    } else {
        vec4 c = texture(u_atlas, v_uv);
        if (c.a < 0.1) discard;
        base = c.rgb;
        alpha = c.a;
    }

    vec3 shaded = apply_shade(base);
    if (u_has_focus == 1 && v_highlight < 0.5) {
        shaded *= DIMMED_FACTOR;
    }

    out_color = vec4(shaded, alpha);
}
