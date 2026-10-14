"""Validated local composition: chroma key, manual motion paths and dip transitions."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class VideoEffects(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key_enabled: bool = False
    key_color: str = Field('#00ff00', pattern=r'^#[0-9a-fA-F]{6}$')
    key_similarity: float = Field(.15, ge=.01, le=.5, allow_inf_nan=False)
    key_blend: float = Field(.05, ge=0, le=.3, allow_inf_nan=False)
    background_color: str = Field('#182438', pattern=r'^#[0-9a-fA-F]{6}$')
    background_id: str = Field('', pattern=r'^(?:[a-f0-9]{32})?$')
    region: Literal['none','blur','image'] = 'none'
    overlay_id: str = Field('', pattern=r'^(?:[a-f0-9]{32})?$')
    x: float = Field(.5, ge=0, le=1, allow_inf_nan=False)
    y: float = Field(.5, ge=0, le=1, allow_inf_nan=False)
    end_x: float = Field(.5, ge=0, le=1, allow_inf_nan=False)
    end_y: float = Field(.5, ge=0, le=1, allow_inf_nan=False)
    width: float = Field(.25, ge=.05, le=1, allow_inf_nan=False)
    height: float = Field(.25, ge=.05, le=1, allow_inf_nan=False)

    @model_validator(mode='after')
    def image_required(self):
        if self.region == 'image' and not self.overlay_id:
            raise ValueError('Upload an overlay image before enabling the image effect.')
        return self


def slice_effects(effects, start, end):
    def point(a, b, t):
        return a+(b-a)*max(0,min(1,t))
    return effects.model_copy(update={
        'x':point(effects.x,effects.end_x,start), 'end_x':point(effects.x,effects.end_x,end),
        'y':point(effects.y,effects.end_y,start), 'end_y':point(effects.y,effects.end_y,end)})


def composition_graph(inputs, vf, grade, effects, width, height, duration, asset, fade_in=0, fade_out=0, fade_color='black'):
    """Return extra inputs and a filter graph; never interpolate user filter expressions."""
    extra, graph = [], [f'[0:v]{vf},fps=30,format=yuv420p[base]']
    current = 'base'
    next_input = inputs.count('-i')

    def image_input(ident):
        nonlocal next_input
        meta, path = asset(ident)
        if meta['kind'] != 'image':
            raise ValueError('Background and overlay assets must be images.')
        idx = next_input
        next_input += 1
        extra.extend(['-loop','1','-framerate','30','-i',str(path)])
        return idx

    if effects.key_enabled:
        if effects.background_id:
            idx = image_input(effects.background_id)
            graph.append(f'[{idx}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1[background]')
        else:
            graph.append(f'color=c={effects.background_color}:s={width}x{height}:r=30[background]')
        graph.append(f'[{current}]format=rgba,colorkey={effects.key_color}:{effects.key_similarity}:{effects.key_blend}[keyed]')
        graph.append('[background][keyed]overlay=shortest=1:format=auto[replaced]')
        current = 'replaced'

    if effects.region != 'none':
        w, h = max(2,round(width*effects.width)//2*2), max(2,round(height*effects.height)//2*2)
        # Start/end percentages describe positions within the remaining frame space.
        x = f'({width-w})*({effects.x}+({effects.end_x-effects.x})*min(t/{duration},1))'
        y = f'({height-h})*({effects.y}+({effects.end_y-effects.y})*min(t/{duration},1))'
        if effects.region == 'blur':
            graph.append(f'[{current}]split[under][sample]')
            graph.append(f"[sample]crop={w}:{h}:x='{x}':y='{y}':exact=1,boxblur=8:2[patch]")
        else:
            idx = image_input(effects.overlay_id)
            graph.append(f'[{current}]null[under]')
            graph.append(f'[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[patch]')
        graph.append(f"[under][patch]overlay=x='{x}':y='{y}':eval=frame:shortest=1[moved]")
        current = 'moved'
    filters = grade.lstrip(',')
    if fade_in:
        filters += f',fade=t=in:st=0:d={fade_in}:color={fade_color}'
    if fade_out:
        filters += f',fade=t=out:st={max(0,duration-fade_out)}:d={fade_out}:color={fade_color}'
    graph.append(f'[{current}]{filters.lstrip(",")+"," if filters.lstrip(",") else ""}format=yuv420p[outv]')
    return extra, ';'.join(graph)
