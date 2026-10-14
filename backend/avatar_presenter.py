"""Local illustrated explainer presenter, rendered with FFmpeg/libass vectors.

Mouth opening follows measured speech energy (not phoneme/realistic lip-sync).
No additional GPU, model downloads, raster dependencies or remote avatar service.
"""
import array
import math
import sys
import textwrap


def stamp(seconds):
    ticks = round(seconds * 100)
    minutes, ticks = divmod(ticks, 6000)
    return f'{minutes//60}:{minutes%60:02}:{ticks//100:02}.{ticks%100:02}'


def safe(text):
    return str(text).replace('\\', '').replace('{', '').replace('}', '').replace('\n', ' ').strip()


def color(hex_color):
    return '&H' + hex_color[4:6] + hex_color[2:4] + hex_color[:2] + '&'


def ellipse(x, y, rx, ry):
    k = .55228475
    return (f'm {x-rx:g} {y:g} b {x-rx:g} {y-k*ry:g} {x-k*rx:g} {y-ry:g} {x:g} {y-ry:g} '
            f'b {x+k*rx:g} {y-ry:g} {x+rx:g} {y-k*ry:g} {x+rx:g} {y:g} '
            f'b {x+rx:g} {y+k*ry:g} {x+k*rx:g} {y+ry:g} {x:g} {y+ry:g} '
            f'b {x-k*rx:g} {y+ry:g} {x-rx:g} {y+k*ry:g} {x-rx:g} {y:g}')


def speech_levels(ffmpeg, voice, duration, speed, run, enabled=True, fps=12):
    """Bounded mono PCM, aligned to the same atempo used by final narration."""
    count = math.ceil(duration*fps)
    if not voice or not enabled:
        return [0.] * count
    raw = run([ffmpeg, '-v', 'error', '-i', str(voice), '-vn', '-af', f'atempo={speed}',
               '-t', str(duration), '-ac', '1', '-ar', '8000', '-f', 's16le', '-'], timeout=120)
    samples = array.array('h')
    samples.frombytes(raw)
    if sys.byteorder != 'little':
        samples.byteswap()
    energies = []
    for frame in range(count):
        part = samples[round(frame*8000/fps):round((frame+1)*8000/fps)]
        energies.append(math.sqrt(sum(v*v for v in part)/max(1,len(part)))/32768)
    peak = max(energies, default=0)
    return [min(1., value/max(.04, peak*.65)) if value > .008 else 0. for value in energies]


def background_filter(width, height):
    """Fit the entire sharp image over a blurred, frame-filling duplicate.

    Only the blurred duplicate is cropped. No black bars or distorted foreground.
    Blur at quarter resolution to keep local CPU rendering inexpensive.
    """
    bw, bh = max(2,width//8*2), max(2,height//8*2)
    return (f'split[pip_bg_src][pip_fg_src];'
            f'[pip_bg_src]scale={bw}:{bh}:force_original_aspect_ratio=increase,'
            f'crop={bw}:{bh},boxblur=10:2,scale={width}:{height},setsar=1[pip_bg];'
            f'[pip_fg_src]scale={width}:{height}:force_original_aspect_ratio=decrease:'
            f'force_divisible_by=2,setsar=1[pip_fg];'
            '[pip_bg][pip_fg]overlay=(W-w)/2:(H-h)/2:shortest=1,setsar=1')


def geometry(width, height, layout):
    """Nonoverlapping foreground controls, with a dedicated caption band.

    Side-by-side uses the complete 320 x 430 drawing. PiP is a small circular
    head-and-shoulders crop over a full-frame image background.
    """
    margin = round(min(width,height)*.035)
    gap = round(min(width,height)*.025)
    left = layout == 'pip-left'
    bottom = height*.83
    if layout != 'side':
        aw = min(width*.14, height*.24) if width/height >= 1.3 else min(width*.22, height*.18)
        visual = (0, 0, width, height)
        text_box = (margin+aw+gap if left else margin, height*.745,
                    width-2*margin-aw-gap, height*.085)
        presenter = (margin if left else width-margin-aw, height-margin-aw, aw)
    elif width/height >= 1.3:
        column = width*(.27 if layout == 'side' else .23)
        content_width = width-2*margin-gap-column
        content_x = margin+column+gap if left else margin
        avatar_x = margin if left else width-margin-column
        aw = min(column, height*(.66 if layout == 'side' else .54)*320/430)
        presenter = (avatar_x+(column-aw)/2, bottom-aw*430/320, aw)
        visual = (content_x, height*.15, content_width, height*.51)
        text_box = (content_x, height*.70, content_width, height*.13)
    else:
        # Stack the image above the presenter/text row on square and tall frames.
        visual = (margin, height*.15, width-2*margin, height*.35)
        aw = min(width*(.38 if layout == 'side' else .32), height*.29*320/430)
        ax = margin if left else width-margin-aw
        presenter = (ax, bottom-aw*430/320, aw)
        text_box = (margin+aw+gap if left else margin, height*.54,
                    width-2*margin-aw-gap, height*.29)
    # Chroma-subsampled media needs even dimensions and offsets for exact placement.
    visual = tuple(int(value)//2*2 for value in visual)
    return visual, presenter, text_box


def caption_box(width, height, layout):
    """Keep subtitles beside a bottom-corner PiP, never across its face."""
    x, right = round(width*.05), round(width*.95)
    if layout in ('pip-left','pip-right'):
        _,(ax,ay,aw),_ = geometry(width,height,layout)
        gap = round(min(width,height)*.025)
        if layout == 'pip-left':
            x = math.ceil(ax+aw+gap)
        else:
            right = math.floor(ax-gap)
    return x, height*.85, right-x, height*.125


def fit_text(items, width, height, preferred_size, minimum_size):
    """Wrap and reduce type before truncating exceptionally long editable text."""
    for size in range(preferred_size, minimum_size-1, -1):
        columns = max(1, int(width/(size*.75)))
        lines = [line for item in items for line in textwrap.wrap(safe(item), width=columns)]
        capacity = max(1, int(height/(size*1.45)))
        if len(lines) <= capacity:
            return lines, size
    lines = lines[:capacity]
    if lines:
        lines[-1] = lines[-1].rstrip(' .')+'…'
    return lines, size


def write_presenter(path, width, height, duration, scene, project, levels, index, total, draw_character=True):
    """Write a slide overlay and animated presenter in one bounded ASS file."""
    visual, (ax,ay,aw), (tx,ty,tw,th) = geometry(width,height,project.presenter_layout)
    compact = project.presenter_layout != 'side'
    scale = aw/(250 if compact else 320)
    clip = ''
    if compact:
        # ASS clipping is in output coordinates; crop the lower torso without
        # moving the face out of the inset. Foreground text stays clear of it.
        clip = '\\clip(' + ellipse(ax+aw/2,ay+aw/2,aw/2,aw/2) + ')'
        ax,ay = ax-35*scale,ay-55*scale
    events = []
    accent = 'A78BFA' if project.presenter_theme == 'indigo' else '45D6BC'
    panel = '242239' if project.presenter_theme == 'indigo' else '173B3B'
    font_size = round(min(width,height)*.042)
    header = f'''[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Nirmala UI,{font_size},&H00FFFFFF,&H00FFFFFF,&H00111111,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    def event(layer, content, start=0, end=None):
        events.append(f'Dialogue: {layer},{stamp(start)},{stamp(duration if end is None else end)},Default,,0,0,0,,{content}')
    def draw(shape, fill, layer=2, start=0, end=None):
        # Zero-area origin anchors all component paths to one common coordinate system.
        event(layer, f'{{\\an7\\pos({ax:.2f},{ay:.2f})\\fscx{scale*100:.3f}\\fscy{scale*100:.3f}{clip}\\bord0\\shad0\\1c{color(fill)}\\p1}}m 0 0 l 0 0 {shape}{{\\p0}}', start, end)
    def text(content, x, y, size, fill='EDF0FA', bold=False):
        event(1, f'{{\\an7\\pos({x:.1f},{y:.1f})\\fs{size}\\b{int(bold)}\\1c{color(fill)}}}{content}')

    if compact:
        # Translucent scrims keep titles, slide points and captions readable on
        # both bright and dark imagery without shrinking the background image.
        for top,bottom in ((0,height*.14),(height*.72,height)):
            event(0, f'{{\\an7\\pos(0,0)\\bord0\\shad0\\1c{color("101724")}\\1a&H78&\\p1}}'
                     f'm 0 0 l 0 0 m 0 {top:g} l {width} {top:g} {width} {bottom:g} 0 {bottom:g}{{\\p0}}')

    margin = round(min(width,height)*.035)
    title = scene.slide_title or project.title
    counter_width = min(width,height)*.14
    title_lines, title_size = fit_text([title], width-2*margin-counter_width,
                                      height*.105, font_size, max(14, font_size//2))
    text('\\N'.join(title_lines), margin, height*.025, title_size, bold=True)
    # Local typography; generated images never need to spell slide text.
    points = scene.slide_points or ([scene.text] if scene.text else [])
    line_size = max(16, round(min(width,height)*.029))
    lines, line_size = fit_text(['• '+safe(point) for point in points], tw, th,
                                line_size, max(14, round(min(width,height)*.018)))
    text('\\N'.join(lines), tx, ty, line_size)
    text(f'{index+1:02} / {total:02}', width-margin-counter_width*.72, height*.04, max(16, font_size//2), accent)

    if not draw_character:
        path.write_text(header+'\n'.join(events)+'\n', encoding='utf-8-sig')
        return visual

    draw(ellipse(160,215,158,205), panel, 2)
    draw(ellipse(160,216,130,165), '33304D' if project.presenter_theme=='indigo' else '214B48', 2)
    # A friendly illustrated presenter with jacket, collar and lapel mic.
    draw('m 45 398 b 43 286 79 274 130 267 l 190 267 b 244 278 278 309 275 398 l 45 398', '5B4BB7' if project.presenter_theme=='indigo' else '23796F', 3)
    draw('m 133 246 l 187 246 188 291 b 172 312 148 312 132 291 l 133 246', 'E5A47E', 4)
    draw('m 131 281 l 160 310 189 281 199 398 120 398', 'EAF0F8', 4)
    draw('m 122 277 l 151 314 134 337 118 311 102 295', accent, 5)
    draw('m 198 277 l 169 314 186 337 202 311 218 295', accent, 5)
    draw(ellipse(106,172,13,22), 'F0B88F', 4)
    draw(ellipse(214,172,13,22), 'F0B88F', 4)
    draw(ellipse(160,166,58,84), 'F6C5A1', 5)
    if project.presenter_character == 'maya':
        draw('m 101 175 b 75 119 97 70 148 73 b 215 61 239 110 222 212 l 210 227 209 145 b 178 145 147 117 131 112 b 119 137 109 152 101 175', '29243A', 6)
    else:
        draw('m 105 150 b 88 115 103 82 127 77 b 151 49 189 77 210 86 b 229 106 220 133 213 147 l 205 117 b 181 124 154 115 139 104 l 115 132 105 150', '29243A', 6)
    draw('m 123 158 b 131 152 142 152 148 157 l 147 161 b 139 158 130 158 123 162', '574033', 7)
    draw('m 174 157 b 181 152 191 152 199 158 l 198 162 b 190 158 182 158 175 161', '574033', 7)
    draw('m 160 171 l 154 192 b 158 196 163 196 168 192', 'DA946F', 7)
    draw(ellipse(123,201,10,5), 'EDAB91', 7)
    draw(ellipse(199,201,10,5), 'EDAB91', 7)
    draw(ellipse(196,326,5,7), '131A2B', 7)
    # Slow hand gestures and blinks remain independent from speech syllables.
    for n in range(0 if compact else math.ceil(duration*2)):
        t, end = n*.5, min(duration,(n+1)*.5)
        offset = 8*math.sin(n*.7)
        draw(f'm 62 346 b 80 361 92 358 111 {319+offset:g} l 95 {308+offset:g} b 80 332 67 325 62 346', 'F6C5A1', 5, t, end)
    for n, level in enumerate(levels):
        start, end = n/12, min(duration,(n+1)/12)
        if start >= duration:
            break
        blink = (start % 3.7) < .16 and start > .3
        for x in (136,186):
            draw(ellipse(x,174,5,1 if blink else 6), '302D40', 8, start,end)
        if level <= .06:
            draw('m 147 213 b 155 221 167 221 176 212 l 175 216 b 166 225 155 225 148 217', '9B4C50', 8,start,end)
        else:
            draw(ellipse(161,217,13,3+level*10), '713541', 8,start,end)
            draw(ellipse(161,221+level*3,7,2+level*2), 'E9909F', 9,start,end)
    path.write_text(header+'\n'.join(events)+'\n', encoding='utf-8-sig')
    return visual
