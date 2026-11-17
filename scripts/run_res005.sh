#!/bin/bash
# RES-005: T2 of muReport on 4 exams, with the QC files to open in ITK-SNAP
# (t2map.mha, roi_t2.mha, labels.txt; and the Dixon segmentation: roi.mha, segmentation.gif).
# Same series as RES-003 (resultats_tests/RES003_series.csv). Run on the station, detached:
#   cd /mnt/rmn_files/Users/IB/mureport
#   nohup bash scripts/run_res005.sh > res005_$(date +%Y%m%d).log 2>&1 &
# Exams: CL2LD260112 (reference exam), CL2OV260828 (only exam acquired head first),
#        CL2OK260630 (manual T2 collapsed on one slice), CL2MF260309 (fattiest exam of the lot).

OUT=resultats_tests/RES005_$(date +%Y%m%d)
for exam in CL2LD260112 CL2OV260828 CL2OK260630 CL2MF260309; do
    grep "^$exam;" resultats_tests/RES003_series.csv |
    while IFS=';' read -r exam segment dixon dixon_desc t2 t2_desc status remark; do
        echo "$(date '+%F %T')  START $exam $segment (T2 series $t2, segmentation on Dixon $dixon)"
        pipeline process -e "$exam" -sd "dicom_lot/$exam" -m t2map_3exp -a "$segment" \
            -s "$t2" -ss "$dixon" -qc-mode global -od "$OUT/$exam" < /dev/null \
            && echo "$(date '+%F %T')  OK    $exam $segment" \
            || echo "$(date '+%F %T')  FAILED $exam $segment"
    done
done
echo "$(date '+%F %T')  done: $OUT"
