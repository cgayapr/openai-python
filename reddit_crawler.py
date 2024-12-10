import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import openai
import praw
import logging

# ===== Setup Logging =====
logging.basicConfig(
    filename="debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ===== Constants and Configuration =====
# Retrieve sensitive information from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Validate environment variables
missing_vars = []
if not OPENAI_API_KEY:
    missing_vars.append("OPENAI_API_KEY")
if not CLIENT_ID or not CLIENT_SECRET or not USER_AGENT:
    missing_vars.append("REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT")

if missing_vars:
    logging.error("Missing environment variables: %s", ", ".join(missing_vars))
    raise EnvironmentError(f"Please set the following environment variables: {', '.join(missing_vars)}")

openai.api_key = OPENAI_API_KEY

# Thresholds and Limits
UPVOTE_THRESHOLD = 5
POST_LIMIT = 200
INITIAL_GOOD_POST_LIMIT = 20
TOP_POSTS_FOR_GPT4 = 10

TIMEFRAME_CONFIG = {
    1: {"label": "Past 3 days", "min_days": 0, "max_days": 3},
    2: {"label": "3 days to 1 week", "min_days": 3, "max_days": 7},
    3: {"label": "1 week to 2 weeks", "min_days": 7, "max_days": 14},
    4: {"label": "2 weeks to 3 weeks", "min_days": 14, "max_days": 21},
}

# ===== Helper Functions =====
def timeframe_condition(choice, created_utc, now):
    """Check if a post falls into the selected timeframe."""
    config = TIMEFRAME_CONFIG.get(choice, TIMEFRAME_CONFIG[1])
    min_seconds = config["min_days"] * 24 * 3600
    max_seconds = config["max_days"] * 24 * 3600
    post_age = now - created_utc
    return min_seconds <= post_age < max_seconds

def fetch_posts(subreddit_name, timeframe_choice, upvote_threshold):
    """Fetch and filter posts based on timeframe and upvotes."""
    try:
        reddit = praw.Reddit(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            user_agent=USER_AGENT,
        )
        logging.info("Successfully initialized Reddit API.")
    except Exception as e:
        logging.exception("Error initializing Reddit API.")
        raise RuntimeError(f"Error initializing Reddit API: {e}")

    now = time.time()
    filtered_posts = []
    try:
        for submission in reddit.subreddit(subreddit_name).new(limit=POST_LIMIT):
            if submission.score < upvote_threshold:
                continue
            if timeframe_condition(timeframe_choice, submission.created_utc, now):
                submission.comments.replace_more(limit=None)
                comments = [c.body for c in submission.comments.list()]
                filtered_posts.append({
                    "id": submission.id,
                    "title": submission.title,
                    "score": submission.score,
                    "url": submission.url,
                    "selftext": submission.selftext,
                    "comments": comments,
                })
        logging.info(f"Fetched {len(filtered_posts)} posts after filtering.")
    except Exception as e:
        logging.exception("Error fetching posts.")
        raise RuntimeError(f"Error fetching posts: {e}")

    return filtered_posts

def summarize_post_for_gpt(post):
    """Create a brief summary of a post for GPT filtering."""
    snippet_comments = "\n".join(post["comments"][:3])
    return f"Post ID: {post['id']}\nTitle: {post['title']}\nScore: {post['score']}\nFirst 3 Comments:\n{snippet_comments}\n------\n"

def filter_good_posts_with_gpt35(posts):
    """Use GPT-3.5-turbo to filter posts."""
    posts_summary = "".join(summarize_post_for_gpt(p) for p in posts)
    prompt = f"""
You are a helpful assistant. Identify up to {INITIAL_GOOD_POST_LIMIT} good posts.

Here are the posts:
{posts_summary}

Return only a comma-separated list of post IDs without any additional text.
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
        )
        # Extract and process the response content
        good_posts_ids = response['choices'][0]['message']['content'].strip()
        good_posts_ids = [pid.strip() for pid in good_posts_ids.split(",") if pid.strip()]
        logging.info(f"GPT-3.5 identified {len(good_posts_ids)} good posts.")
        return [p for p in posts if p["id"] in good_posts_ids]
    except Exception as e:
        logging.exception("Error filtering posts with GPT-3.5.")
        raise RuntimeError(f"Error filtering posts with GPT-3.5: {e}")

def deep_analysis_with_gpt4(posts, subreddit_name):
    """Perform deeper analysis on top posts using GPT-4."""
    try:
        top_posts_text = "\n\n".join(summarize_post_for_gpt(p) for p in posts[:TOP_POSTS_FOR_GPT4])
        prompt = f"""
Analyze these posts from r/{subreddit_name}:

{top_posts_text}
"""

        response = openai.Chat.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.7,
        )
        # Correctly accessing the message content
        analysis = response.choices[0].message["content"].strip()
        logging.info("GPT-4 analysis completed successfully.")
        return analysis
    except Exception as e:
        logging.exception("Error with GPT-4 analysis.")
        raise RuntimeError(f"Error with GPT-4 analysis: {e}")

# ===== GUI Setup =====
def run_script():
    """Fetch posts, filter, and analyze them."""
    try:
        text_output.delete("1.0", tk.END)
        subreddit_name = subreddit_entry.get().strip()

        if not subreddit_name:
            raise ValueError("Subreddit name cannot be empty!")

        text_output.insert(tk.END, f"Fetching posts from r/{subreddit_name}...\n")
        text_output.update()

        # Initialize progress bar
        progress_bar['value'] = 0
        progress_bar['maximum'] = 100
        progress_bar.update()

        posts = fetch_posts(subreddit_name, timeframe_var.get(), UPVOTE_THRESHOLD)
        progress_bar['value'] = 20

        if not posts:
            text_output.insert(tk.END, "No posts found within the selected timeframe.\n")
            progress_bar['value'] = 100
            return

        text_output.insert(tk.END, f"Found {len(posts)} posts. Filtering with GPT-3.5...\n")
        text_output.update()

        good_posts = filter_good_posts_with_gpt35(posts)
        progress_bar['value'] = 50

        if not good_posts:
            text_output.insert(tk.END, "No 'good' posts identified by GPT-3.5.\n")
            progress_bar['value'] = 100
            return

        text_output.insert(tk.END, f"Analyzing top {len(good_posts)} posts with GPT-4...\n")
        text_output.update()

        analysis_result = deep_analysis_with_gpt4(good_posts, subreddit_name)
        progress_bar['value'] = 80

        text_output.insert(tk.END, "===== ANALYSIS COMPLETE =====\n")
        text_output.insert(tk.END, analysis_result)
        progress_bar['value'] = 100

    except Exception as e:
        text_output.insert(tk.END, f"An error occurred: {str(e)}\n")
        logging.exception("Error in run_script")
        progress_bar['value'] = 100
        messagebox.showerror("Error", str(e))
    finally:
        text_output.update()
        progress_bar.update()

def run_script_thread():
    """Run the script in a separate thread to keep the GUI responsive."""
    threading.Thread(target=run_script, daemon=True).start()

# ===== Main GUI Code =====
def create_gui():
    root = tk.Tk()
    root.title("Reddit Crawler")
    root.geometry("800x600")

    frame = ttk.Frame(root, padding="10")
    frame.pack(fill=tk.BOTH, expand=True)

    # Subreddit label and entry
    subreddit_label = ttk.Label(frame, text="Subreddit:")
    subreddit_label.grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
    subreddit_entry = ttk.Entry(frame, width=30)
    subreddit_entry.grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)

    # Timeframe selection
    timeframe_label = ttk.Label(frame, text="Select Timeframe:")
    timeframe_label.grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
    timeframe_var = tk.IntVar(value=1)
    timeframe_frame = ttk.Frame(frame)
    timeframe_frame.grid(column=1, row=1, sticky=tk.W, padx=5, pady=5)
    for i, config in TIMEFRAME_CONFIG.items():
        ttk.Radiobutton(
            timeframe_frame,
            text=config["label"],
            variable=timeframe_var,
            value=i
        ).pack(anchor=tk.W)

    # Run button
    run_button = ttk.Button(frame, text="Run Analysis", command=run_script_thread)
    run_button.grid(column=0, row=2, columnspan=2, pady=10)

    # Output area
    text_output = tk.Text(frame, width=100, height=25, wrap=tk.WORD, state=tk.NORMAL)
    text_output.grid(column=0, row=3, columnspan=2, padx=5, pady=5, sticky="nsew")

    # Make the text_output expandable
    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(1, weight=1)

    # Progress Bar
    progress_bar = ttk.Progressbar(frame, orient="horizontal", length=400, mode="determinate")
    progress_bar.grid(column=0, row=4, columnspan=2, pady=10, padx=5, sticky="ew")

    # Initialize text_output and progress_bar in the global scope
    globals()['subreddit_entry'] = subreddit_entry
    globals()['timeframe_var'] = timeframe_var
    globals()['text_output'] = text_output
    globals()['progress_bar'] = progress_bar

    # Welcome message
    text_output.insert(tk.END, "Welcome to Reddit Crawler! Please enter a subreddit to start.\n")

    return root

if __name__ == "__main__":
    try:
        root = create_gui()
        root.mainloop()
    except Exception as e:
        logging.exception("An unexpected error occurred in the main GUI loop.")
        messagebox.showerror("Fatal Error", f"An unexpected error occurred: {e}")
