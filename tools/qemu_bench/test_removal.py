import tarfile, io, subprocess, os
os.chdir("/tmp")
B="/mnt/c/Users/emili/Desktop/gbos-x1p/downloads/tools/erofs-1.9.4/bin"
# tar 1: dir + file
with tarfile.open("t1.tar","w",format=tarfile.PAX_FORMAT) as t:
    d=tarfile.TarInfo("."); d.type=tarfile.DIRTYPE; d.mode=0o755; t.addfile(d)
    f=tarfile.TarInfo("keep.txt"); b=b"hello"; f.size=len(b); f.mode=0o644; t.addfile(f, io.BytesIO(b))
    x=tarfile.TarInfo("remove.txt"); x.size=len(b"bye"); x.mode=0o644; t.addfile(x, io.BytesIO(b"bye"))
subprocess.run([B+"/mkfs.erofs","-T123456","test.erofs","t1.tar"],check=True,capture_output=True)
# tar 2: removal
with tarfile.open("t2.tar","w",format=tarfile.PAX_FORMAT) as t:
    r=tarfile.TarInfo("remove.txt"); r.type=b"D"; r.uid=r.gid=0; r.uname=r.gname=""; t.addfile(r)
p=subprocess.run([B+"/mkfs.erofs","--incremental=test.erofs","--tar=f","-T123456","test2.erofs","t2.tar"],capture_output=True,text=True)
print("mkfs rc:",p.returncode, p.stdout[-200:], p.stderr[-200:])
p2=subprocess.run([B+"/fsck.erofs","--device=test2.erofs","-p","remove.txt","test2.erofs"],capture_output=True,text=True)
print("fsck remove.txt rc:",p2.returncode, p2.stdout[-150:], p2.stderr[-150:])
