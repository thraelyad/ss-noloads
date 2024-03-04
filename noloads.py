import cv2
import numpy as np
import os
from queue import Queue

def remove_small_circle(frame, rectangle_size=200):
    # Get the center coordinates of the frame, and move y down 20 pixels to account for the required asymmetric cropping
    center_x, center_y = frame.shape[1] // 2, frame.shape[0] // 2 + 20

    # Calculate the coordinates
    x1 = max(0, center_x - rectangle_size // 2)
    y1 = max(0, center_y - rectangle_size // 2)
    x2 = min(frame.shape[1], center_x + rectangle_size // 2)
    y2 = min(frame.shape[0], center_y + rectangle_size // 2)

    # Draw a black rectangle on the frame, but match with whatever gray intensity the origin has (to account for variation in videos)
    intensity = frame[0,0]
    frame[y1:y2, x1:x2] = intensity

    return frame


def remove_cursor(frame, cursor_template):
    res = cv2.matchTemplate(frame, cursor_template, cv2.TM_CCOEFF_NORMED)
    h,w = cursor_template.shape[::-1] # switch from row-major to column-major

    loc = np.where(res >= .8) # threshold is .8
    for pt in zip(*loc[::-1]):  # Switch columns and rows
        # fill in cursor with black
        cv2.rectangle(frame, pt, (pt[0] + w, pt[1] + h), 0, -1)
    return frame

# Todo: check if load was less than 10 frames. If it was, go back and don't count it
def video_to_frames(input_loc, output_loc, crop_region):
    try:
        os.mkdir(output_loc)
    except OSError:
        pass
    
    # Start capturing the feed and declare variables up here for scope reasons
    VAR_THRESHOLD = 0.015
    crop_vals = crop_region.split(":")
    cap = cv2.VideoCapture(input_loc)
    frameCount = 0
    cursor_template = cv2.imread("cursor.png", cv2.IMREAD_GRAYSCALE)
    voidoutCounter = 0
    firstFrameAfterVoidEnd = False
    prevFrame = None
    cropped = None
    prevFrameVariance = 0
    loadCounter = 0
    frames = Queue(maxsize=6) # useful data structure to store frames

    print("\nConverting video (this may take a while) ...")

    while cap.isOpened():
        # Extract the frame
        ret, frame = cap.read()
        if(ret is False):
            # Release the feed
            cap.release()
            break
        # maybe re-add histogram equalization?
        # cropped_image = image[y:y+h,x:x+h]
        frames.put(frame)
        cropped = frame[int(crop_vals[1]):int(crop_vals[1])+int(crop_vals[3]), int(crop_vals[0]):int(crop_vals[0])+int(crop_vals[2])]
        if(frameCount == 0): prevFrame = cropped
        #gray = cv2.fastNlMeansDenoising(cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY))
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        nocursor = remove_cursor(gray, cursor_template)
        #print(str(frameCount) + " var: " + str(np.var(frame)))

        # note: if you have an EXTREMELY dirty signal, you may need to change this 5 to something higher. but likely no change is needed.
        # this checks the variance (standard deviation squared) of all the frame's pixels. 
        # loading seems all seem to have roughly variance of < 0.015, but rouglhy 1.5 for gray frames
        # and no other frames really get close

        avgIntensity = np.mean(nocursor)
        frameVariance = np.var(nocursor)

        # i really need to toss this logic into a function LOL. do calculations on current frame and return the "previous" values
        # potential todo: change variance to only be calculated if intensity is within the threshold. could result in a slight speedup
        print("var no circle: ", np.var(remove_small_circle(prevFrame)))
        if(voidoutCounter == 0): # If not a voidout frame,
            if((frameVariance < VAR_THRESHOLD and avgIntensity < 50) or (frameVariance < VAR_THRESHOLD * 100 and avgIntensity > 100) ): # If loading frame (check using different variance thresholds for black/grey frames)
                if(firstFrameAfterVoidEnd): # If a void animation just occurred,
                    # load frame was misinterpreted as a void frame, and we need to go overwrite 64 frames + 2 extra
                    # to get back to the first all-black voidout frame (only occurs Faron->Lanayru fly) 
                    frameCount -= 66          
                elif(prevFrameVariance >= VAR_THRESHOLD and np.var(remove_small_circle(prevFrame)) < VAR_THRESHOLD): # previous frame was the beginning of a void animation (note that voidouts are always all-black)
                    print(frameCount, " is first all-black voidout frame. Begin tracking.")
                    voidoutCounter = 64 # voids are roughly 60 frames, plus 4 for leniency
                else: # Otherwise it's a real loading frame, and we should skip it
                    print("Skipped " + str(frameCount) + " (var " + str(frameVariance) + ")")
                    firstFrameAfterVoidEnd = False
                    loadCounter += 1
                    continue
            else: # If not a loading frame
                print("Frame ", str(frameCount), "var ", str(frameVariance), " avgIntensity ", avgIntensity)
                if(loadCounter > 0 and loadCounter <= 6): # this was not a real load
                    print("Fake load discovered")
                    #frameCount -= 6 # only uncomment this if you comment out continue (for analysis of skipped frames)
                    while not frames.empty():
                        print("Writing to ", frameCount, " to unskip load.")
                        cv2.imwrite(output_loc + "/%#06d.jpg" % (frameCount), frames.get()) # "un-skip" the fake load
                        frameCount += 1
                loadCounter = 0

            firstFrameAfterVoidEnd = False
        else: # If voidout frame
            print("Frame ", frameCount, ", voidoutCounter ", voidoutCounter)
            voidoutCounter -= 1
            if(voidoutCounter == 0): firstFrameAfterVoidEnd = True
            
        prevFrame = nocursor
        prevFrameVariance = frameVariance
        cv2.imwrite(output_loc + "/%#06d.jpg" % (frameCount), frame)
        frameCount += 1


def rebuild_video(input_loc, output_loc):
    os.system("cd " + output_loc + " & ffmpeg.exe -framerate 30 -i %06d.jpg -c:v libx264 -pix_fmt yuv420p " + output_filename)
    # move result back up to this directory
    os.system("mv " + output_loc + "/" + output_filename + " .")
    # delete temp files
    #os.system("del trimmed-" + input_loc)
    #os.system("rmdir " + output_loc + " /s /q")

# Start of execution - get user input
input_loc = input("Enter input file name: ")
output_loc = input_loc + "_temp"
start_time = input("Enter starting timestamp (at least 5 seconds before run begins) in format \"HH:MM:SS\": ")
end_time = input("Enter ending timestamp (at least 5 seconds after run ends) in format \"HH:MM:SS\": ")
crop_region = input("Enter values of cropped region in \"X:Y:W:H\" format: ")

# ask about building a video
output_filename = None
toBuild = input("Do you want to build a video, or just frame-count with the images? Enter \"y\", or \"n\": ")
if(toBuild == "y"):
    output_filename = input("Enter output video name: ")

# Trim, then force to 30fps:
os.system("ffmpeg.exe -ss " + start_time + " -to " + end_time + " -i " + input_loc + " -c:v copy -c:a copy -f nut - | ffmpeg.exe -f nut -i - -vf \"fps=30\" -c:a copy trimmed-" + input_loc)

# the magic part
video_to_frames("trimmed-" + input_loc, output_loc, crop_region)
#video_to_frames(input_loc, output_loc, crop_region)

# now put all images back together into a video, if user requested:
if(toBuild == "y"):
    rebuild_video(input_loc, output_loc)
