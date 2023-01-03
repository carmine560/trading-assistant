from datetime import datetime
import os
import shutil
import sys

def backup_file(source, backup_root=None, number_of_backups=-1):
    if os.path.exists(source):
        if not backup_root:
            backup_root = os.path.join(os.path.dirname(__file__), 'backups')

        if number_of_backups:
            if not os.path.isdir(backup_root):
                try:
                    os.makedirs(backup_root)
                except OSError as e:
                    print(e)
                    sys.exit(1)

            backup = os.path.join(
                backup_root,
                os.path.splitext(os.path.basename(source))[0]
                + datetime.fromtimestamp(
                    os.path.getmtime(source)).strftime('-%Y%m%dT%H%M%S')
                + os.path.splitext(source)[1])
            if not os.path.exists(backup):
                try:
                    shutil.copy2(source, backup)
                except Exception as e:
                    print(e)
                    sys.exit(1)

            if number_of_backups > 0:
                backups = os.listdir(backup_root)
                for f in backups[:len(backups) - number_of_backups]:
                    try:
                        os.remove(os.path.join(backup_root, f))
                    except OSError as e:
                        print(e)
                        sys.exit(1)
        else:
            if os.path.isdir(backup_root):
                try:
                    shutil.rmtree(backup_root)
                except Exception as e:
                    print(e)
                    sys.exit(1)
