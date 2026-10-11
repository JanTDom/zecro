"""Deterministic logo analysis and grid-aware masthead geometry."""
from __future__ import annotations
from pathlib import Path
import re
from PIL import Image
from ..models.schemas import LogoProfile, TitleDNA

def analyze_logo(path: str | Path, *, asset_ref: str | None = None, variant: str = "primary") -> LogoProfile:
    p=Path(path); vector=p.suffix.lower() in {".svg",".pdf",".eps",".ai"}
    ratio=None; bbox=None; colors=[]
    if vector and p.suffix.lower()==".svg":
        raw=p.read_text(encoding="utf-8",errors="ignore")
        match=re.search(r'<svg[^>]*(?:viewBox="([^"]+)"|width="([^"]+)"[^>]*height="([^"]+)")',raw,re.I)
        if match:
            values=(match.group(1) or "").split()
            if len(values)==4 and float(values[3]): ratio=float(values[2])/float(values[3])
        colors=list(dict.fromkeys(re.findall(r'#[0-9a-fA-F]{6}',raw)))[:8]
    else:
        try:
            with Image.open(p) as im:
                ratio=im.width/im.height if im.height else None
                alpha=im.getchannel("A") if "A" in im.getbands() else None
                if alpha:
                    bbox=list(alpha.getbbox() or (0,0,im.width,im.height)); bbox=[round(bbox[0]/im.width,4),round(bbox[1]/im.height,4),round(bbox[2]/im.width,4),round(bbox[3]/im.height,4)]
                colors=["#%02x%02x%02x" % pixel[:3] for pixel in im.convert("RGB").resize((1,1)).getdata()]
        except Exception: pass
    layout="horizontal" if (ratio or 1.0) >= 2.2 else "side" if (ratio or 1.0) < .8 else "ears"
    return LogoProfile(asset_ref=asset_ref,variant=variant,aspect_ratio=ratio,content_bbox=bbox,dominant_colors=colors,layout_mode=layout,vector=vector,clear_space_mm=3.0,approved=False)

def masthead_geometry(dna: TitleDNA, profile: LogoProfile | None, page_width_mm: float, *, zone: str = "front_page") -> dict[str,float|str]:
    grid=dna.grid; base=max(.1,float(grid.baseline_grid_pt)*.352778)
    if not profile: return {"mode":"horizontal","x":dna.format.margin_left_mm,"y":dna.format.margin_top_mm,"w":page_width_mm-dna.format.margin_left_mm-dna.format.margin_right_mm,"h":round(max(12,base*8)/base)*base}
    mode=profile.layout_mode if zone=="front_page" else ("side" if profile.layout_mode=="side" else "horizontal")
    h=base*(10 if mode=="horizontal" else 12 if mode=="ears" else 18)
    w=page_width_mm-dna.format.margin_left_mm-dna.format.margin_right_mm
    if mode=="side": w=min(w*.22,max(20,profile.min_width_mm or 24))
    return {"mode":mode,"x":dna.format.margin_left_mm,"y":dna.format.margin_top_mm,"w":round(w,2),"h":round(h,2)}
