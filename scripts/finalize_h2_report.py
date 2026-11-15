"""Finalize prose rounding from measured values; preserve earlier report stages."""
import json
from h2_final_common import *
def main():
    verify_manifest(OUT/'interpretation');data=json.loads((OUT/'analysis/summary.json').read_text());text=(OUT/'interpretation/final_research_report.md').read_text()
    replacements={'43.909s':f'{data["summary"]["rdao_v2"]["wall_s_total"]:.3f}s','11.754s':f'{data["summary"]["periodic5"]["wall_s_total"]:.3f}s'}
    for old,new in replacements.items():text=text.replace(old,new)
    text+='\nFinal report note: wall-time prose rounding was corrected directly from summary.json (RDAO v2 and Periodic5); raw data, tables, analysis and conclusions are unchanged. Earlier automatic/interpretation reports remain preserved. The canonical final copy is final_report/research_report.md. Reproduction finishes with finalize_h2_report.py.\n'
    target=OUT/'final_report';target.mkdir(exist_ok=False);(target/'research_report.md').write_text(text)
    write(target/'rounding_corrections.json',{'scope':'Two prose-only wall-time rounding corrections; no data/model/protocol changes','replacements':replacements})
    (ROOT/'docs/h2_final_research_report.md').write_text(text);manifest(target)
if __name__=='__main__':main()
