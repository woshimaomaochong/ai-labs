#!/bin/bash
# 语音第二期：$1 = adult|kid，$2.. = 模型（a8 bz vox cosy qwen）
export HOME=/work MODELSCOPE_CACHE=/work/models/ms HF_HUB_OFFLINE=1
if [ "$1" = adult ]; then REF=/work/ref/adult_ref.wav; TXT="希望你以后能够做的比我还好呦。"; P=v2a
else REF=/work/ref/kid_ref.wav; TXT="（参考录音的原文，按实际念的内容填）"; P=v2k; fi
shift
one(){ # 模型 标签 ；附加环境变量由调用处给
  case $1 in
    a8)   /work/venv_a8/bin/python /work/run_audio8.py $REF "$TXT" $2 ;;
    bz)   /work/venv_bz/bin/python /work/run_breezy.py $REF "$TXT" $2 ;;
    vox)  /work/venv_vox/bin/python /work/run_voxcpm.py $REF "$TXT" $2 ;;
    qwen) /work/venv_qwen/bin/python /work/run_qwen3.py $REF "$TXT" $2 ;;
    cosy) (cd /work/CosyVoice && /work/venv_cosy/bin/python /work/run_cosy.py $REF "$TXT" $2) ;;
  esac
}
for m in "$@"; do
  TEXTS=/work/texts.json one $m ${P} > /work/logs/${P}_$m.log 2>&1 && echo "RUN $m ${P} ok" || echo "RUN $m ${P} FAIL"
  TEXTS=/work/texts2.json one $m ${P}tw > /work/logs/${P}tw_$m.log 2>&1 && echo "RUN $m ${P}tw ok" || echo "RUN $m ${P}tw FAIL"
  TEXTS=/work/texts_num.json HARD_REPS=3 one $m ${P}num > /work/logs/${P}num_$m.log 2>&1 && echo "RUN $m ${P}num ok" || echo "RUN $m ${P}num FAIL"
  TEXTS=/work/texts.json WHOLE_REPEAT=5 one $m ${P}rep > /work/logs/${P}rep_$m.log 2>&1 && echo "RUN $m ${P}rep ok" || echo "RUN $m ${P}rep FAIL"
done
echo ALL_DONE
