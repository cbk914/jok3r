sudo docker pull koutto/jok3r
sudo docker run -i -t --name jok3r-container-updated -w /root/jok3r -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix --shm-size 2g --net=host koutto/jok3r
