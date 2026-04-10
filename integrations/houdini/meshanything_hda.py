"""
Houdini: add this folder's parent (integrations) to HOUDINI_PYTHONPATH, or copy
`meshanything_client` next to this file and append:

  import sys
  sys.path.append("/path/to/integrations/meshanything_client")

Then in a Python SOP or Python Script (HDA), after writing a mesh to OBJ:

  import meshanything_hda as ma
  ma.optimize_file("/tmp/in.obj", "/tmp/out.obj")

Or set env MESHANYTHING_API_BASE / MESHANYTHING_API_KEY before calling.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Default: integrations/meshanything_client on sys.path (set in Houdini env)
_here = Path(__file__).resolve().parent
_integrations = _here.parent
_client = _integrations / "meshanything_client"
if _client.is_dir() and str(_client) not in sys.path:
    sys.path.insert(0, str(_client))

from meshanything_client import ClientConfig, MeshAnythingClient  # noqa: E402
from meshanything_client.errors import MeshAnythingAPIError  # noqa: E402


def optimize_file(
    input_obj_path: str,
    output_obj_path: str,
    *,
    mc: bool = False,
    mc_level: int = 7,
    sampling: bool = False,
    seed: int = 0,
) -> str:
    """Call Space API and write optimized OBJ to ``output_obj_path``. Returns output path."""
    cfg = ClientConfig.from_env()
    client = MeshAnythingClient(cfg)
    result = client.optimize_file(
        input_obj_path,
        input_type="mesh",
        mc=mc,
        mc_level=mc_level,
        sampling=sampling,
        seed=seed,
    )
    client.save_result(result, output_obj_path)
    return output_obj_path


def optimize_with_hou_dialog() -> None:
    """Example: call from Houdini shelf after selecting a File SOP path."""
    import hou

    try:
        optimize_file(
            os.environ["MESHANYTHING_INPUT_OBJ"],
            os.environ["MESHANYTHING_OUTPUT_OBJ"],
        )
    except KeyError as e:
        raise hou.Error(
            "Set MESHANYTHING_INPUT_OBJ and MESHANYTHING_OUTPUT_OBJ, "
            "and MESHANYTHING_API_BASE"
        ) from e
    except MeshAnythingAPIError as e:
        raise hou.Error(str(e)) from e
