#===--fare_utils.py---------------------------------------------------===//
# Part of the Startup-Demos Project, under the MIT License
# See https://github.com/qualcomm/Startup-Demos/blob/main/LICENSE.txt
# for license information.
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: MIT License
#===----------------------------------------------------------------------===//

import sqlite3
from pathlib import Path

def get_fare_and_platform(source, destination, ticket_count):
    fare_db_path = Path(__file__).resolve().parents[2] / 'modules' / 'db' / 'fares.db'

    conn = sqlite3.connect(fare_db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT fare, platform FROM fares WHERE source=? AND destination=?', (source, destination))
    result = cursor.fetchone()
    conn.close()

    if result:
        single_fare, platform = result
        return single_fare * ticket_count, platform
    else:
        print(f"?? No fare found for route: {source} ? {destination}")
        return 0, 1  # Default fare and platform

