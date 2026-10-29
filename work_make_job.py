import importlib.util, json, pathlib, os
spec=importlib.util.spec_from_file_location("fh", "scripts/ffmpeg_helpers.py")
fh=importlib.util.module_from_spec(spec); spec.loader.exec_module(fh)
p=pathlib.Path('work/ffmpeg_demo').resolve()
frames=sorted(p.glob('src_*.png'))
j=fh.build_job_json(source_frames=[str(f) for f in frames[:2]], reference_frames=[str(frames[2])] if len(frames)>2 else [str(frames[0])], output_cube=str(p/'out.cube'), report_json=str(p/'report.json'), iterations=30)
open(p/'job.json','w').write(json.dumps(j,indent=2))
print('job ok')
