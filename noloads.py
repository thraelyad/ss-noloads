import cv2
import numpy as np
import os

def remove_cursor(frame, cursor_template):
    res = cv2.matchTemplate(frame, cursor_template, cv2.TM_CCOEFF_NORMED)
    h,w = cursor_template.shape[::-1] # switch from row-major to column-major

    loc = np.where(res >= .8) # threshold is .8
    for pt in zip(*loc[::-1]):  # Switch columns and rows
        # fill in cursor with black
        cv2.rectangle(frame, pt, (pt[0] + w, pt[1] + h), 0, -1)
    return frame

def video_to_frames(input_loc, output_loc):
    try:
        os.mkdir(output_loc)
    except OSError:
        pass

    # Start capturing the feed
    cap = cv2.VideoCapture(input_loc)
    count = 0
    cursor_template = cv2.imread("cursor.png", cv2.IMREAD_GRAYSCALE)

    print("\nConverting video (this may take a while) ...")

    while cap.isOpened():
        # Extract the frame
        ret, frame = cap.read()
        if(ret is False):
            # Release the feed
            cap.release()
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        nocursor = remove_cursor(gray, cursor_template)
        #print(str(count) + " var: " + str(np.var(frame)))
        # note: if you have an EXTREMELY dirty signal, you may need to change this 7 to something higher. but likely no change is needed.
        # this checks the variance (standard deviation squared) of all the frame's pixels. loading seems all seem to have roughly variance of < 5 (+2 for leniency)
        # and no other frames really get close except for transitions between loading zones, which are fine to get rid of.
        if(np.var(frame) < 7):
            #print("Skipped " + str(count) + " (var " + str(np.var(frame)) + ")")
            continue

        # Write the results back to output location
        cv2.imwrite(output_loc + "/%#06d.jpg" % (count+1), frame)
        count += 1

def rebuild_video(input_loc, output_loc):
    os.system("cd " + output_loc + " & ffmpeg.exe -framerate 30 -i %06d.jpg -c:v libx264 -pix_fmt yuv420p " + output_filename)
    # move result back up to this directory
    os.system("mv " + output_loc + "/" + output_filename + " .")
    # delete temp files
    os.system("del cropped-" + input_loc)
    os.system("rmdir " + output_loc + " /s /q")

# Start of execution - get user input
input_loc = input("Enter input file name: ")
output_loc = input_loc + "_temp"
start_time = input("Enter starting timestamp (at least 5 seconds before run begins) in format \"HH:MM:SS\": ")
end_time = input("Enter ending timestamp (at least 5 seconds after run ends) in format \"HH:MM:SS\": ")
cropregion = input("Enter w, h, x, and y of cropped region in \"W:H:X:Y\" format: ")

# ask about building a video
output_filename = None
toBuild = input("Do you want to build a video, or just frame-count with the images? Enter \"y\", or \"n\": ")
if(toBuild == "y"):
    output_filename = input("Enter output video name: ")

# Trim, then crop and force to 30fps:
os.system("ffmpeg.exe -ss " + start_time + " -to " + end_time + " -i " + input_loc + " -c:v copy -c:a copy -f nut - | ffmpeg.exe -f nut -i - -vf \"fps=30,crop=" + cropregion + "\" -c:a copy cropped-" + input_loc)

# the magic part
video_to_frames("cropped-" + input_loc, output_loc)

# now put all images back together into a video, if user requested:
if(toBuild == "y"):
    rebuild_video(input_loc, output_loc)
