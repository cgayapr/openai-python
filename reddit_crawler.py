import os
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import praw
import logging
from openai import OpenAI
import json #Search funcitonality   
import webbrowser   #search functionality.
from scrapy.crawler import CrawlerProcess
from reddit_scraper.reddit_scraper.spiders.news_spider import NewsSpider


# ===== Setup Logging =====
logging.basicConfig(
    filename="debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# ===== Constants and Configuration =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT")

# Validate environment variables
missing_vars = []
if not OPENAI_API_KEY:
    missing_vars.append("OPENAI_API_KEY")
if not REDDIT_CLIENT_ID:
    missing_vars.append("REDDIT_CLIENT_ID")
if not REDDIT_CLIENT_SECRET:
    missing_vars.append("REDDIT_CLIENT_SECRET")
if not REDDIT_USER_AGENT:
    missing_vars.append("REDDIT_USER_AGENT")

if missing_vars:
    logging.error("Missing environment variables: %s", ", ".join(missing_vars))
    raise EnvironmentError(f"Please set the following environment variables: {', '.join(missing_vars)}")

# Initialize OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)

# Thresholds and Limits
UPVOTE_THRESHOLD = 5
POST_LIMIT = 200
INITIAL_GOOD_POST_LIMIT = 20
TOP_POSTS_FOR_ANALYSIS = 10

# Timeframe Configuration
TIMEFRAME_CONFIG = {
    1: {"label": "Past 3 days", "min_days": 0, "max_days": 3},
    2: {"label": "3 days to 1 week", "min_days": 3, "max_days": 7},
    3: {"label": "1 week to 2 weeks", "min_days": 7, "max_days": 14},
    4: {"label": "2 weeks to 3 weeks", "min_days": 14, "max_days": 21},
}

# ===== Helper Functions =====
def is_post_in_timeframe(choice: int, created_utc: float, current_time: float) -> bool:
    """Check if a post falls into the selected timeframe."""
    config = TIMEFRAME_CONFIG.get(choice, TIMEFRAME_CONFIG[1])
    min_seconds = config["min_days"] * 24 * 3600
    max_seconds = config["max_days"] * 24 * 3600
    post_age = current_time - created_utc
    return min_seconds <= post_age < max_seconds

def fetch_subreddit_posts(subreddit_name: str, timeframe_choice: int, upvote_threshold: int) -> list:
    """Fetch and filter posts based on timeframe and upvotes."""
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        logging.info("Successfully connected to the Reddit API.")
    except Exception as e:
        logging.exception("Error connecting to Reddit API.")
        raise RuntimeError(f"Reddit API initialization failed: {e}")

    current_time = time.time()
    filtered_posts = []
    try:
        for submission in reddit.subreddit(subreddit_name).new(limit=POST_LIMIT):
            if submission.score < upvote_threshold:
                continue
            if is_post_in_timeframe(timeframe_choice, submission.created_utc, current_time):
                submission.comments.replace_more(limit=None)
                comments = [comment.body for comment in submission.comments.list()]
                post_data = {
                    "id": submission.id,
                    "title": submission.title,
                    "score": submission.score,
                    "url": submission.url,
                    "selftext": submission.selftext,
                    "comments": comments,
                }
                filtered_posts.append(post_data)
                # Debug: Log fetched posts
                print(f"DEBUG: Fetched Post - Title: {submission.title}, Upvotes: {submission.score}, URL: {submission.url}")
        logging.info(f"Fetched and filtered {len(filtered_posts)} posts.")
    except Exception as e:
        logging.exception("Error fetching posts.")
        raise RuntimeError(f"Error fetching posts: {e}")

    return filtered_posts

    """Fetch and filter posts based on timeframe and upvotes."""
    try:
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        logging.info("Successfully connected to the Reddit API.")
    except Exception as e:
        logging.exception("Error connecting to Reddit API.")
        raise RuntimeError(f"Reddit API initialization failed: {e}")

    current_time = time.time()
    filtered_posts = []
    try:
        for submission in reddit.subreddit(subreddit_name).new(limit=POST_LIMIT):
            if submission.score < upvote_threshold:
                continue
            if is_post_in_timeframe(timeframe_choice, submission.created_utc, current_time):
                submission.comments.replace_more(limit=None)
                comments = [comment.body for comment in submission.comments.list()]
                filtered_posts.append({
                    "id": submission.id,
                    "title": submission.title,
                    "score": submission.score,
                    "url": submission.url,
                    "selftext": submission.selftext,
                    "comments": comments,
                })
        logging.info(f"Fetched and filtered {len(filtered_posts)} posts.")
    except Exception as e:
        logging.exception("Error fetching posts.")
        raise RuntimeError(f"Error fetching posts: {e}")

    return filtered_posts

def summarize_post(post: dict) -> str:
    """Create a brief summary of a post for GPT filtering."""
    snippet_comments = "\n".join(post["comments"][:3])
    return (
        f"Post ID: {post['id']}\n"
        f"Title: {post['title']}\n"
        f"Score: {post['score']}\n"
        f"First 3 Comments:\n{snippet_comments}\n"
        "------\n"
    )

def filter_posts_with_gpt(posts: list) -> list:
    """Filter posts with GPT-3.5."""
    posts_summary = "".join(summarize_post(post) for post in posts)
    
    # Debug: Log the posts summary sent to GPT
    print("DEBUG: Posts summary sent to GPT for filtering:\n", posts_summary)
    
    prompt = f"""
    You are a helpful assistant. Identify up to {INITIAL_GOOD_POST_LIMIT} good posts.

    Here are the posts:
    {posts_summary}

    Return only a comma-separated list of post IDs without any additional text.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        # Debug: Log GPT response
        print("DEBUG: GPT Response:\n", response.choices[0].message.content)
        
        message_content = response.choices[0].message.content.strip()
        good_posts_ids = [pid.strip() for pid in message_content.split(",") if pid.strip()]
        logging.info(f"GPT-3.5 identified {len(good_posts_ids)} good posts.")
        return [post for post in posts if post["id"] in good_posts_ids]
    except Exception as e:
        logging.exception("Error during filtering with GPT.")
        raise RuntimeError(f"Error during filtering: {e}")

    """Filter posts with GPT-3.5."""
    posts_summary = "".join(summarize_post(post) for post in posts)
    prompt = f"""
    You are a helpful assistant. Identify up to {INITIAL_GOOD_POST_LIMIT} good posts.

    Here are the posts:
    {posts_summary}

    Return only a comma-separated list of post IDs without any additional text.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )
        # Access the correct response attribute
        message_content = response.choices[0].message.content.strip()
        good_posts_ids = [pid.strip() for pid in message_content.split(",") if pid.strip()]
        logging.info(f"GPT-3.5 identified {len(good_posts_ids)} good posts.")
        return [post for post in posts if post["id"] in good_posts_ids]
    except Exception as e:
        logging.exception("Error during filtering with GPT.")
        raise RuntimeError(f"Error during filtering: {e}")



def analyze_posts_with_gpt4(posts: list, subreddit_name: str) -> str:
    """Perform deeper analysis on top posts using GPT-4o."""
    try:
        top_posts_text = "\n\n".join(summarize_post(post) for post in posts[:TOP_POSTS_FOR_ANALYSIS])
        
        # Debug: Log posts sent to GPT-4 for analysis
        print("DEBUG: Posts sent to GPT-4 for analysis:\n", top_posts_text)
        
        prompt = f"""
        Analyze these posts from r/{subreddit_name}:

        {top_posts_text}

        Provide insights, trends, or recommendations based on these posts.
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
            temperature=0.7,
        )
        # Debug: Log GPT-4 response
        print("DEBUG: GPT-4 Response:\n", response.choices[0].message.content)
        
        analysis = response.choices[0].message.content.strip()
        logging.info("GPT-4 analysis completed successfully.")
        return analysis
    except Exception as e:
        logging.exception("Error during analysis with GPT-4.")
        raise RuntimeError(f"Error during analysis: {e}")

    """Perform deeper analysis on top posts using GPT-4o."""
    try:
        top_posts_text = "\n\n".join(summarize_post(post) for post in posts[:TOP_POSTS_FOR_ANALYSIS])
        prompt = f"""
        Analyze these posts from r/{subreddit_name}:

        {top_posts_text}

        Provide insights, trends, or recommendations based on these posts.
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=3000,
            temperature=0.7,
        )
        # Access the correct response attribute
        analysis = response.choices[0].message.content.strip()
        logging.info("GPT-4 analysis completed successfully.")
        return analysis
    except Exception as e:
        logging.exception("Error during analysis with GPT-4.")
        raise RuntimeError(f"Error during analysis: {e}")


def fetch_latest_news(keyword):
    """Fetch the latest news articles using NewsSpider and update the progress bar."""
    try:
        # Reset the progress bar
        progress_bar["value"] = 0
        progress_bar.update()

        output_file = "news_results.json"
        if os.path.exists(output_file):
            os.remove(output_file)  # Remove previous results if they exist

        # Define a Scrapy process
        process = CrawlerProcess(settings={
            "FEEDS": {output_file: {"format": "json"}},
            "LOG_LEVEL": "ERROR",  # Reduce noise in logs
        })

        def run_spider():
            # Run the spider in the background
            process.crawl("news_spider", keyword=keyword)
            process.start()
            progress_bar["value"] = 100  # Mark the progress bar as complete

        # Start the Scrapy process in a thread to keep the GUI responsive
        threading.Thread(target=run_spider, daemon=True).start()

        # Increment progress bar over time (simulated updates)
        for i in range(1, 101, 10):  # Increment by 10% every second
            time.sleep(1)
            progress_bar["value"] = i
            progress_bar.update()

        # Load and return results from the JSON file
        if os.path.exists(output_file):
            with open(output_file, "r") as file:
                return json.load(file)
        else:
            return []
    except Exception as e:
        logging.exception("Error fetching news with NewsSpider.")
        messagebox.showerror("Error", f"Error fetching news: {e}")
        return []


def load_search_history():
    """Load search history from a file."""
    try:
        with open("search_history.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def save_search_history(history):
    """Save search history to a file."""
    with open("search_history.json", "w") as file:
        json.dump(history, file)

def add_to_history(topic, results):
    """Add a new search result to the history."""
    history = load_search_history()
    history.append({"topic": topic, "results": results})
    save_search_history(history)

def display_history():
    """Display search history in the GUI."""
    history_list.delete(0, tk.END)
    for entry in load_search_history():
        history_list.insert(tk.END, entry["topic"])

def open_selected_history():
    """Open selected history topic results and display them."""
    selected_index = history_list.curselection()
    if not selected_index:
        messagebox.showerror("Error", "No history item selected!")
        return

    # Reset the history tab progress bar
    history_progress_bar["value"] = 0
    history_progress_bar.update()

    # Get the selected topic
    selected_topic = history_list.get(selected_index)
    history = load_search_history()

    # Search for the topic in the history
    for entry in history:
        if entry["topic"] == selected_topic:
            try:
                # Update progress bar midway
                history_progress_bar["value"] = 50
                history_progress_bar.update()

                # Clear the results area in the History Tab
                results_text.delete("1.0", tk.END)

                # Display the results
                for i, result in enumerate(entry["results"], start=1):
                    results_text.insert(tk.END, f"{i}. {result['title']}\n{result['url']}\n\n")

                # Complete the progress bar
                history_progress_bar["value"] = 100
                history_progress_bar.update()
                return
            except Exception as e:
                logging.exception("Error displaying history results.")
                messagebox.showerror("Error", f"An error occurred: {e}")
                history_progress_bar["value"] = 100
                history_progress_bar.update()
                return

    # If no results are found for the topic
    messagebox.showinfo("No Results", f"No results found for topic: {selected_topic}")
    history_progress_bar["value"] = 100
    history_progress_bar.update()



def fetch_news_for_topic():
    """Fetch and display news for the entered topic."""
    topic = topic_entry.get().strip()
    if not topic:
        messagebox.showerror("Error", "Topic cannot be empty!")
        return

    try:
        results = fetch_latest_news(topic)  # Fetch using NewsSpider
        if results:
            add_to_history(topic, results)
            update_results(results)
            display_history()
        else:
            messagebox.showinfo("No Results", f"No news found for topic: {topic}")
    except Exception as e:
        logging.exception("Error fetching news with NewsSpider.")
        messagebox.showerror("Error", f"Error fetching news: {e}")


def update_results(results):
    """Update the results display with news links."""
    results_text.delete("1.0", tk.END)
    for i, result in enumerate(results, 1):
        results_text.insert(tk.END, f"{i}. {result['title']}\n{result['link']}\n\n")

def fetch_relevant_links(topics):
    """
    Takes a list of topics/keywords and runs the Scrapy spider for each keyword.
    """
    process = CrawlerProcess(settings={
        "FEEDS": {
            "output.json": {"format": "json"},  # Save results to a JSON file
        },
        "LOG_LEVEL": "ERROR",  # Optional: Reduce log noise
    })

    # Run the Scrapy spider for each keyword
    for topic in topics:
        print(f"Scraping links for topic: {topic}...")
        process.crawl(NewsSpider, keyword=topic)
    
    process.start()  # Block until all spiders complete
    print("Scraping complete!")
def run_script():
    """Main function to fetch posts, filter them, and analyze using GPT."""
    try:
        run_button.config(state=tk.DISABLED)  # Disable the button while running
        text_output.delete("1.0", tk.END)
        subreddit_name = subreddit_entry.get().strip()

        if not subreddit_name:
            raise ValueError("Subreddit name cannot be empty!")

        # Fetch posts from the subreddit
        text_output.insert(tk.END, f"Fetching posts from r/{subreddit_name}...\n")
        text_output.update()
        main_progress_bar['value'] = 0
        main_progress_bar.update()

        posts = fetch_subreddit_posts(subreddit_name, timeframe_var.get(), UPVOTE_THRESHOLD)
        main_progress_bar['value'] = 30
        main_progress_bar.update()

        if not posts:
            text_output.insert(tk.END, "No posts found in the selected timeframe.\n")
            main_progress_bar['value'] = 100
            return

        # Filter posts with GPT
        text_output.insert(tk.END, "Filtering posts with GPT...\n")
        text_output.update()
        good_posts = filter_posts_with_gpt(posts)
        main_progress_bar['value'] = 60
        main_progress_bar.update()

        if not good_posts:
            text_output.insert(tk.END, "No good posts found after GPT filtering.\n")
            main_progress_bar['value'] = 100
            return

        # Analyze posts with GPT
        text_output.insert(tk.END, f"Analyzing {len(good_posts)} top posts...\n")
        text_output.update()
        analysis = analyze_posts_with_gpt4(good_posts, subreddit_name)
        main_progress_bar['value'] = 100
        main_progress_bar.update()

        # Display the analysis
        text_output.insert(tk.END, "\n===== ANALYSIS COMPLETE =====\n", "bold")
        text_output.tag_configure("bold", font=("Arial", 12, "bold"))

        text_output.insert(tk.END, "### Insights:\n", "header")
        text_output.tag_configure("header", font=("Arial", 14, "bold"))

        # Add more spacing for sections
        # Display the analysis dynamically
        if analysis:
            text_output.insert(tk.END, f"{analysis}\n", "body")
            text_output.tag_configure("body", font=("Arial", 12))
        else:
            text_output.insert(tk.END, "No insights were generated from the analysis.\n", "body")
            text_output.tag_configure("body", font=("Arial", 12))


# Continue adding headers and descriptions for other sections.


    except Exception as e:
        logging.exception("Error during analysis.")
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        run_button.config(state=tk.NORMAL)  # Re-enable the button

def run_script_thread():
    """Run the main script in a separate thread to keep the GUI responsive."""
    threading.Thread(target=run_script, daemon=True).start()
    
# ================================================== Enhanced GUI Setup =================================================================
def create_gui():
    """Create the enhanced GUI for the Reddit Crawler."""
    root = tk.Tk()
    root.title("Reddit Crawler")
    root.geometry("900x700")
    
    # Create Tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True)

    # Main Analysis Tab
    analysis_frame = ttk.Frame(notebook)
    notebook.add(analysis_frame, text="Main Analysis")

    # History Tab
    history_frame = ttk.Frame(notebook)
    notebook.add(history_frame, text="History")

    # ===== Main Analysis Tab Components =====
    frame = ttk.Frame(analysis_frame, padding="10")
    frame.pack(fill=tk.BOTH, expand=True)

    # Subreddit Input
    ttk.Label(frame, text="Subreddit:", font=("Arial", 12, "bold")).grid(column=0, row=0, sticky=tk.W, padx=5, pady=5)
    subreddit_entry = ttk.Entry(frame, width=40)
    subreddit_entry.grid(column=1, row=0, sticky=tk.W, padx=5, pady=5)

    # Timeframe Selection
    ttk.Label(frame, text="Select Timeframe:", font=("Arial", 12, "bold")).grid(column=0, row=1, sticky=tk.W, padx=5, pady=5)
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

    # Run Analysis Button
    run_button = ttk.Button(frame, text="Run Analysis", command=run_script_thread)
    run_button.grid(column=0, row=2, columnspan=2, pady=10)

    # Results Output for Main Analysis
    text_output = tk.Text(frame, wrap=tk.WORD, height=20, state=tk.NORMAL, font=("Arial", 12))
    text_output.grid(column=0, row=3, columnspan=2, padx=5, pady=5, sticky="nsew")
    frame.rowconfigure(3, weight=1)
    frame.columnconfigure(1, weight=1)

    # Progress Bar for Main Analysis Tab
    main_progress_bar = ttk.Progressbar(frame, orient="horizontal", length=400, mode="determinate")
    main_progress_bar.grid(column=0, row=4, columnspan=2, pady=10, padx=5, sticky="ew")

    # ===== History Tab Components =====
    history_list_frame = ttk.Frame(history_frame, padding="10")
    history_list_frame.pack(fill=tk.BOTH, expand=True)
    
    # History List
    history_list = tk.Listbox(history_list_frame, height=20)
    history_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # History Results Text
    results_text = tk.Text(history_list_frame, wrap=tk.WORD, height=20, state=tk.NORMAL, font=("Arial", 12))
    results_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # View Selected Button
    ttk.Button(history_frame, text="View Selected", command=open_selected_history).pack(pady=5)
    
    # Progress Bar for History Tab
    history_progress_bar = ttk.Progressbar(history_frame, orient="horizontal", length=400, mode="determinate")
    history_progress_bar.pack(pady=5, padx=5, fill=tk.X)

    # Global References for Event Handling
    globals().update({
        'subreddit_entry': subreddit_entry,
        'timeframe_var': timeframe_var,
        'text_output': text_output,
        'history_list': history_list,
        'results_text': results_text,
        'run_button': run_button,
        'main_progress_bar': main_progress_bar,
        'history_progress_bar': history_progress_bar,
    })

    return root


# ===== Search History Functions =====
def display_history():
    """Display search history in the listbox."""
    history_list.delete(0, tk.END)
    for entry in load_search_history():
        history_list.insert(tk.END, entry["topic"])


# ===== Main Execution =====
if __name__ == "__main__":
    try:
        root = create_gui()
        display_history()  # Load history on startup
        root.mainloop()
    except Exception as e:
        logging.exception("Fatal error in GUI.")
        messagebox.showerror("Fatal Error", str(e)) #