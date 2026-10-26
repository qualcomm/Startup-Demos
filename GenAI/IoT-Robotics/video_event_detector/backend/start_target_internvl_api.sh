#===--start_target_internvl_api.sh----------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT
#===----------------------------------------------------------------------===//

#!/usr/bin/env bash
set -euo pipefail

_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_root_dir="$(cd "$_script_dir/.." && pwd)"
_env_target="${INTERNVL_ENV_TARGET:-$_root_dir/executorch_building/common/env_target.sh}"

if [[ -f "$_env_target" ]]; then
  # shellcheck disable=SC1090
  source "$_env_target"
fi

_python_executable="${PYTHON_EXECUTABLE:-python3}"
_model_dir="${INTERNVL_MODEL_DIR:-$_root_dir/models/internvl/deploy}"
_runner_bin="${RUNNER_BIN:-$_model_dir/qnn_multimodal_persistent_runner}"
_decoder_path="${DECODER_PATH:-$_model_dir/hybrid_llama_qnn.pte}"
_tok_embedding_path="${TOK_EMBEDDING_PATH:-$_model_dir/tok_embedding_qnn.pte}"
_encoder_path="${ENCODER_PATH:-$_model_dir/vision_encoder_qnn.pte}"
_tokenizer_path="${TOKENIZER_PATH:-$_model_dir/tokenizer.json}"
_decoder_model_version="${DECODER_MODEL_VERSION:-internvl3}"
_eval_mode="${EVAL_MODE:-1}"
_seq_len="${SEQ_LEN:-1024}"
_host="${HOST:-0.0.0.0}"
_port="${PORT:-8080}"

if [[ -d "$_model_dir" ]]; then
  export LD_LIBRARY_PATH="$_model_dir:${LD_LIBRARY_PATH:-}"
fi

if [[ -z "${ADSP_LIBRARY_PATH:-}" ]] && [[ -d /usr/lib/dsp/cdsp ]]; then
  export ADSP_LIBRARY_PATH="/usr/lib/dsp/cdsp;/usr/lib/rfsa/adsp;/dsp"
fi

if [[ -z "${CDSP_LIBRARY_PATH:-}" ]] && [[ -n "${ADSP_LIBRARY_PATH:-}" ]]; then
  export CDSP_LIBRARY_PATH="$ADSP_LIBRARY_PATH"
fi

require_file() {
  local path=$1
  local description=$2
  local hint=$3

  if [[ -f "$path" ]]; then
    return 0
  fi

  echo "[start_target_internvl_api] $description not found: $path" >&2
  echo "[start_target_internvl_api] set $hint to override it." >&2
  exit 1
}

if [[ ! -x "$_runner_bin" ]]; then
  echo "[start_target_internvl_api] persistent multimodal runner not found: $_runner_bin" >&2
  echo "[start_target_internvl_api] set RUNNER_BIN to override it." >&2
  exit 1
fi

require_file "$_decoder_path" "decoder path" "DECODER_PATH"
require_file "$_tok_embedding_path" "token embedding path" "TOK_EMBEDDING_PATH"
require_file "$_encoder_path" "encoder path" "ENCODER_PATH"
require_file "$_tokenizer_path" "tokenizer path" "TOKENIZER_PATH"

exec "$_python_executable" "$_script_dir/qnn_internvl_api.py" \
  --host "$_host" \
  --port "$_port" \
  --runner-binary "$_runner_bin" \
  --decoder-path "$_decoder_path" \
  --tok-embedding-path "$_tok_embedding_path" \
  --encoder-path "$_encoder_path" \
  --tokenizer-path "$_tokenizer_path" \
  --decoder-model-version "$_decoder_model_version" \
  --eval-mode "$_eval_mode" \
  --seq-len "$_seq_len" \
  "$@"
