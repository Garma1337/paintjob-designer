#version 330 core

// Half-Lambert wrap so the dark side isn't pitch-black; an ambient floor keeps
// triangles facing away from the light still legible.

in vec2 v_uv;
in vec3 v_normal;
in float v_highlight;
in vec3 v_vcolor;

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

// Untextured triangles carry the sentinel UV (-1, -1) from AtlasUvMapper and
// render using the per-vertex Gouraud color directly.
//
// Textured triangles get the PSX GPU's texture-modulation: `final = 2 * vcolor
// * texture`, where vcolor = 0.5 (128/255) is the neutral tint that displays
// the texture as-authored. Many CTR meshes store greyscale texture templates
// that rely on this modulation to come out fur/skin-colored at runtime — with
// a flat passthrough those polys show up as literal grey.
void main() {
    vec3 base;
    float alpha;

    if (v_uv.x < 0.0) {
        base = v_vcolor;
        alpha = 1.0;
    } else {
        vec4 c = texture(u_atlas, v_uv);
        if (c.a < 0.1) discard;
        base = clamp(c.rgb * v_vcolor * 2.0, 0.0, 1.0);
        alpha = c.a;
    }

    vec3 shaded = apply_shade(base);
    if (u_has_focus == 1 && v_highlight < 0.5) {
        shaded *= DIMMED_FACTOR;
    }

    out_color = vec4(shaded, alpha);
}
