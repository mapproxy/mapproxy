# This file is part of the MapProxy project.
# Copyright (C) 2010 Omniscale <http://omniscale.de>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from mapproxy.seed.util import format_cleanup_task
from mapproxy.util import cleanup_directory

def cleanup(tasks, concurrency=2, dry_run=False, skip_geoms_for_last_levels=0,
               verbose=True):
    for task in tasks:
        print format_cleanup_task(task)
        
        if not task.coverage:
            simple_cleanup(task, dry_run=dry_run)
        else:
            print 'not cleaning up'

def simple_cleanup(cleanup_task, dry_run=False):
    for level in cleanup_task.levels:
        level_dir = cleanup_task.tile_manager.cache.level_location(level)
        if dry_run:
            def file_handler(filename):
                print 'removing ' + filename
        else:
            file_handler = None
        print 'removing oldfiles in ' + level_dir
        cleanup_directory(level_dir, cleanup_task.remove_timestamp,
            file_handler=file_handler)