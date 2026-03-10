# Understanding `seed_clusters.py`

The `seed_clusters.py` script is a specialized mock data generator. Its purpose is to create "intelligent" or **clustered** interaction data that mimics how real human beings behave on a video platform, rather than just generating pure random clicks. 

This is crucial for training our Machine Learning (PyTorch Two-Tower) model, because neural networks need recognizable patterns to learn from. If the data is 100% random, the model learns nothing (which is why earlier training epochs kept rejecting the new weights).

Here is a step-by-step breakdown of exactly what the script does:

## 1. Connecting and Fetching Data
First, it connects to the PostgreSQL database and fetches all the existing Users and Videos. Crucially, it also grouped the videos by their **categories** (e.g., Gaming, Vlogs, Education, Comedy).

## 2. Assigning "Personas" to Users
Real people have preferences. To simulate this, the script loops through all 50 mock users and assigns each one a "Favorite Category" (which we call a Persona). 
* For example, User 1 might be assigned "Gaming".
* User 2 might be assigned "Comedy".

## 3. Generating 30,000 Clustered Events
The script generates 30,000 new interaction events (like Views, Likes, and Skips). But instead of assigning them randomly, it uses a weighted probability engine to enforce the User Personas:

* **The 85% Rule (The "Happy Path"):**
  85% of the time, the script picks a video from the user's Favorite Category. Because the user "loves" this content, the script forces them to produce **Positive Signals**:
  * They have a 60% chance to View it deeply (watch ratio between 75% and 100%).
  * They have a 30% chance to Like it.
  * They have a 10% chance to Share it.

* **The 15% Rule (The "Explore/Dislike Path"):**
  15% of the time, the script simulates the user scrolling onto a random video outside their niche. Because they aren't interested in this category, the script forces **Negative Signals**:
  * They have a 40% chance to immediately Skip it.
  * They have a 30% chance to Dislike it.
  * Their View duration is heavily penalized (watch ratio is forced between 0% and 25%).

## 4. Why Does This Matter?
By writing 30,000 rows of this highly correlated behavior into the `events` table, we hand PyTorch a massive set of mathematically solvable patterns. 

When the **Two-Tower Model** spins up its training cycle, its gradient descent algorithm will notice that User 1's embeddings frequently align with Gaming video embeddings, and push them closer together in the vector space. The model's Cross-Entropy Validation Loss will drop dramatically because it can finally successfully "predict" that User 1 will like the next Gaming video they see. 

Because this new model correctly maps behavioral clusters, it will easily beat the 1% improvement threshold and successfully overwrite the live `.pt` weights file used by the API!
