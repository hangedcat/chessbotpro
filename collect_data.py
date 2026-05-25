import os
import cv2
import numpy as np
import mss
import time

# Create dataset folders
CLASSES = ['empty', 'wp', 'wn', 'wb', 'wr', 'wq', 'wk', 'bp', 'bn', 'bb', 'br', 'bq', 'bk']
DATASET_DIR = "dataset"
for c in CLASSES:
    os.makedirs(os.path.join(DATASET_DIR, c), exist_ok=True)

# Starting board representation (8x8)
# Row 0 is black pieces, Row 7 is white pieces
START_BOARD = [
    ['br', 'bn', 'bb', 'bq', 'bk', 'bb', 'bn', 'br'],
    ['bp', 'bp', 'bp', 'bp', 'bp', 'bp', 'bp', 'bp'],
    ['empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty'],
    ['empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty'],
    ['empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty'],
    ['empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty', 'empty'],
    ['wp', 'wp', 'wp', 'wp', 'wp', 'wp', 'wp', 'wp'],
    ['wr', 'wn', 'wb', 'wq', 'wk', 'wb', 'wn', 'wr']
]

def find_board_in_row(row_bgr, width):
    row = row_bgr.astype(np.int16)
    diffs = np.sqrt(np.sum((row[1:].astype(float) - row[:-1].astype(float))**2, axis=1))
    trans = np.where(diffs > 25)[0]
    if len(trans) < 7:
        return None
    merged = [trans[0]]
    for t in trans[1:]:
        if t - merged[-1] > 5:
            merged.append(t)
    if len(merged) < 7:
        return None
    for i in range(len(merged) - 6):
        bounds = merged[i:i+7]
        gaps = [bounds[j+1] - bounds[j] for j in range(6)]
        avg = sum(gaps) / 6
        if avg < 40 or avg > 300:
            continue
        if not all(abs(g - avg) < avg * 0.12 for g in gaps):
            continue
        sq_size = int(round(avg))
        x_start = bounds[0] - sq_size
        x_end = bounds[-1] + sq_size
        if x_start < 0 or x_end >= width:
            continue
        mids = [x_start + int(sq_size * (j + 0.5)) for j in range(8)]
        colors = [row_bgr[min(m, width-1)].astype(int) for m in mids]
        evens = np.array([colors[j] for j in range(0, 8, 2)])
        odds = np.array([colors[j] for j in range(1, 8, 2)])
        if np.max(np.std(evens, axis=0)) < 15 and np.max(np.std(odds, axis=0)) < 15:
            avg_even = np.mean(evens, axis=0)
            avg_odd = np.mean(odds, axis=0)
            if np.sqrt(np.sum((avg_even - avg_odd)**2)) > 30:
                return (x_start, sq_size)
    return None

def auto_detect_board():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = np.array(sct.grab(monitor))
    screen_h, screen_w = screenshot.shape[:2]
    bgr = screenshot[:, :, :3]
    
    row_hits = []
    for y in range(0, screen_h, 3):
        result = find_board_in_row(bgr[y], screen_w)
        if result:
            row_hits.append((y, result[0], result[1]))
            
    if len(row_hits) < 10:
        return None
        
    groups = []
    current = [row_hits[0]]
    for hit in row_hits[1:]:
        prev = current[-1]
        if abs(hit[1] - prev[1]) < 10 and abs(hit[2] - prev[2]) < 5 and hit[0] - prev[0] < 15:
            current.append(hit)
        else:
            if len(current) >= 10:
                groups.append(current)
            current = [hit]
    if len(current) >= 10:
        groups.append(current)
        
    if not groups:
        return None
        
    best = max(groups, key=len)
    x_start = int(np.median([h[1] for h in best]))
    sq_size = int(np.median([h[2] for h in best]))
    board_size = sq_size * 8
    
    # Grid alignment vertical refinement
    y_center = (best[0][0] + best[-1][0]) // 2
    y_rough = y_center - board_size // 2
    
    col_x = x_start + sq_size // 2
    col_x = min(col_x, screen_w - 1)
    
    # Sample column pixels around the estimated board area
    y_min = max(0, y_rough - sq_size // 2)
    y_max = min(screen_h - 1, y_rough + board_size + sq_size // 2)
    
    col_pixels = bgr[y_min:y_max, col_x].astype(float)
    # Compute gradient (absolute color difference between adjacent vertical pixels)
    grads = np.mean(np.abs(col_pixels[1:] - col_pixels[:-1]), axis=1)
    
    best_dy = 0
    max_grad = -1
    
    # Search for the best alignment dy within [-sq_size/2, sq_size/2]
    for dy in range(-sq_size // 2, sq_size // 2):
        current_grad = 0
        valid = True
        for i in range(9):
            grid_y = y_rough + dy + i * sq_size
            idx = grid_y - y_min
            if 0 <= idx < len(grads):
                current_grad += grads[idx]
            else:
                valid = False
        if valid and current_grad > max_grad:
            max_grad = current_grad
            best_dy = dy
            
    y_start_refined = max(0, y_rough + best_dy)
    return (x_start, y_start_refined, board_size, board_size, sq_size)

def get_square_corners_bg(square_img):
    h, w = square_img.shape[:2]
    # Sample 5x5 corners
    corners = np.concatenate([
        square_img[0:5, 0:5],
        square_img[0:5, w-5:w],
        square_img[h-5:h, 0:5],
        square_img[h-5:h, w-5:w]
    ], axis=0)
    return np.mean(corners, axis=(0, 1))

def swap_background(img, src_bg, target_bg):
    # Calculate distance to source background color
    dist = np.linalg.norm(img.astype(float) - src_bg, axis=2)
    # Mask where pixel is close to background (threshold of 40 is standard)
    mask = dist < 45
    
    out = img.copy()
    out[mask] = target_bg
    return out

def capture_and_save(bbox):
    x, y, w, h, sq = bbox
    with mss.mss() as sct:
        monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
        img = np.array(sct.grab(monitor))[:, :, :3]  # BGR
        
    timestamp = int(time.time() * 1000)
    
    # 1. Identify light and dark square colors using empty squares on row 2 (which are empty in start pos)
    # Row 2, Col 0 and Row 2, Col 1
    sq_2_0 = img[2*sq : 3*sq, 0 : sq]
    sq_2_1 = img[2*sq : 3*sq, sq : 2*sq]
    
    bg_2_0 = get_square_corners_bg(sq_2_0)
    bg_2_1 = get_square_corners_bg(sq_2_1)
    
    # Determine which is light based on luminance
    lum_2_0 = 0.299 * bg_2_0[2] + 0.587 * bg_2_0[1] + 0.114 * bg_2_0[0]
    lum_2_1 = 0.299 * bg_2_1[2] + 0.587 * bg_2_1[1] + 0.114 * bg_2_1[0]
    
    if lum_2_0 > lum_2_1:
        light_bg = bg_2_0
        dark_bg = bg_2_1
    else:
        light_bg = bg_2_1
        dark_bg = bg_2_0
        
    print(f"Detected light square color: {light_bg.astype(int)}, dark: {dark_bg.astype(int)}")
    
    count = 0
    for row in range(8):
        for col in range(8):
            label = START_BOARD[row][col]
            y1 = row * sq
            y2 = (row + 1) * sq
            x1 = col * sq
            x2 = (col + 1) * sq
            
            square_img = img[y1:y2, x1:x2]
            square_img_resized = cv2.resize(square_img, (64, 64))
            
            # Save original image
            filename = f"{label}_{timestamp}_{row}_{col}.png"
            filepath = os.path.join(DATASET_DIR, label, filename)
            cv2.imwrite(filepath, square_img_resized)
            count += 1
            
            # If it's a piece, generate a synthetic swapped-background version!
            if label != 'empty':
                # Determine current background of the square
                curr_bg = get_square_corners_bg(square_img_resized)
                curr_lum = 0.299 * curr_bg[2] + 0.587 * curr_bg[1] + 0.114 * curr_bg[0]
                
                # If current square is closer to light, swap to dark. Otherwise swap to light.
                dist_to_light = np.linalg.norm(curr_bg - light_bg)
                dist_to_dark = np.linalg.norm(curr_bg - dark_bg)
                
                if dist_to_light < dist_to_dark:
                    target_bg = dark_bg
                else:
                    target_bg = light_bg
                    
                synthetic_img = swap_background(square_img_resized, curr_bg, target_bg)
                
                # Save synthetic image
                syn_filename = f"{label}_{timestamp}_{row}_{col}_synthetic.png"
                syn_filepath = os.path.join(DATASET_DIR, label, syn_filename)
                cv2.imwrite(syn_filepath, synthetic_img)
                count += 1
            
    print(f"Captured and generated {count} total square images (original + background-swapped).")

def main():
    print("=========================================")
    print("Chess Piece Data Collector - Background Swapping Enabled")
    print("Make sure your board is in the STARTING POSITION on screen.")
    print("=========================================")
    
    import shutil
    if os.path.exists(DATASET_DIR):
        ans = input("Dataset folder already exists. Clear it and start fresh? (y/n): ")
        if ans.strip().lower() == 'y':
            shutil.rmtree(DATASET_DIR)
            for c in CLASSES:
                os.makedirs(os.path.join(DATASET_DIR, c), exist_ok=True)
            print("Existing dataset cleared.")
    
    bbox = None
    while bbox is None:
        print("Detecting chessboard...")
        bbox = auto_detect_board()
        if bbox is None:
            print("Board not detected. Make sure the board is fully visible.")
            input("Press Enter to try again...")
            
    print(f"Board detected! x={bbox[0]}, y={bbox[1]}, size={bbox[2]}px")
    
    print("\nInstructions:")
    print("1. Leave the board in STARTING position.")
    print("2. You can click on different squares to add highlights (yellow/red/etc.).")
    print("3. You can change themes or piece styles.")
    print("4. Press Enter to capture, or type 'q' to quit.")
    
    capture_count = 0
    while True:
        user_input = input(f"Press Enter to capture screenshot #{capture_count + 1} (or 'q' to quit): ")
        if user_input.strip().lower() == 'q':
            break
        
        # Re-detect in case board moved
        current_bbox = auto_detect_board()
        if current_bbox is None:
            print("Failed to detect board. Did you cover or move it?")
            continue
            
        capture_and_save(current_bbox)
        capture_count += 1

if __name__ == "__main__":
    main()
