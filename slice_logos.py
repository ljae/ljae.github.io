
from PIL import Image, ImageOps
import os

def slice_logos(image_path, output_dir):
    # Load image
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"Error: Could not load image {image_path}: {e}")
        return

    # Create output directory if not exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Convert to RGBA
    img = img.convert("RGBA")
    
    # Create a mask for non-transparent pixels (assuming transparency indicates boundaries)
    # If the background is white, we might need to invert.
    # Let's inspect the alpha channel.
    data = img.getdata()
    
    # Simple projection to find rows and columns
    width, height = img.size
    
    # We will look for separate blobs. A robust way without cv2 is flood filling or connected components.
    # identifying unconnected non-white/non-transparent regions.
    
    # Let's assume white or transparent background.
    # Convert to grayscale for thresholding
    gray = img.convert("L")
    # Invert so content is white, background is black (assuming white background)
    # Check top-left pixel to guess background color
    bg_color = gray.getpixel((0,0))
    if bg_color > 200: # Light background
        thresh = ImageOps.invert(gray)
    else:
        thresh = gray

    # binary threshold
    thresh = thresh.point(lambda p: 255 if p > 50 else 0)
    
    # simple bounding box of the whole thing isn't enough.
    # We need connected components. 
    # Since we can't easily do connected components with just PIL without recursion limits or complexity,
    # let's try a heuristic: horizontal and vertical projection profiles.
    
    # Get bounding box of all content
    bbox = thresh.getbbox()
    if not bbox:
        print("No content found.")
        return

    content = img.crop(bbox)
    # Re-obtain thresh for the crop
    thresh_crop = thresh.crop(bbox)
    
    # Scan from left to right to find gaps
    w, h = content.size
    col_has_content = [0] * w
    for x in range(w):
        for y in range(h):
            if thresh_crop.getpixel((x, y)) > 0:
                col_has_content[x] = 1
                break
                
    # Find raw segments first
    raw_segments = []
    in_segment = False
    start_x = 0
    for x in range(w):
        if col_has_content[x]:
            if not in_segment:
                in_segment = True
                start_x = x
        else:
            if in_segment:
                in_segment = False
                raw_segments.append((start_x, x))
    
    if in_segment:
        raw_segments.append((start_x, w))

    print(f"Found {len(raw_segments)} raw segments.")
    
    # Merge segments
    merged_segments = []
    if raw_segments:
        curr_start, curr_end = raw_segments[0]
        
        MERGE_THRESHOLD = 50
        
        for i in range(1, len(raw_segments)):
            next_start, next_end = raw_segments[i]
            if next_start - curr_end < MERGE_THRESHOLD:
                # Merge
                curr_end = next_end
            else:
                # Finalize current
                merged_segments.append((curr_start, curr_end))
                curr_start = next_start
                curr_end = next_end
        
        # Append last
        merged_segments.append((curr_start, curr_end))

    print(f"Found {len(merged_segments)} merged segments.")
    
    saved_files = []
    
    for i, (sx, ex) in enumerate(merged_segments):
        # Allow some padding
        pad = 10 # increased padding
        
        # Ensure we don't go out of bounds with padding but also don't include other logos
        # Since gaps are ~120, a pad of 10 is safe.
        
        final_x = max(0, sx - pad)
        final_w = min(w, ex + pad) - final_x
        
        # Extract
        segment_crop = content.crop((final_x, 0, final_x + final_w, h))
        
        # Trim vertical whitespace
        segment_bbox = segment_crop.getbbox()
        if segment_bbox:
            final_logo = segment_crop.crop(segment_bbox)
            
            # Save
            filename = f"logo_{i+1}.png"
            filepath = os.path.join(output_dir, filename)
            final_logo.save(filepath)
            saved_files.append(filename)
            print(f"Saved {filepath}")

    return saved_files

if __name__ == "__main__":
    slice_logos("assets/company_logo.png", "assets/sliced_logos")
