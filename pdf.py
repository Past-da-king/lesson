import matplotlib.pyplot as plt
import numpy as np

# Assuming O is at the origin (0,0) and it's a right angle
# Let's pick some arbitrary lengths for the legs s and q
s_length = 3
q_length = 4

# Coordinates of the vertices
O = (0, 0)
S = (-s_length, 0) # Place S on the negative x-axis
Q = (0, q_length)  # Place Q on the positive y-axis

# Calculate the length of the hypotenuse p
p_length = np.sqrt(s_length**2 + q_length**2)

# Create the plot
fig, ax = plt.subplots(figsize=(6, 6))

# Draw the lines forming the triangle
ax.plot([O[0], S[0]], [O[1], S[1]], 'k-') # Line O to S (side s)
ax.plot([O[0], Q[0]], [O[1], Q[1]], 'k-') # Line O to Q (side q)
ax.plot([S[0], Q[0]], [S[1], Q[1]], 'k-') # Line S to Q (side p)

# Plot the vertices as points
ax.plot(O[0], O[1], 'ko')
ax.plot(S[0], S[1], 'ko')
ax.plot(Q[0], Q[1], 'ko')

# Add vertex labels
ax.text(O[0] - 0.2, O[1] - 0.3, 'O', fontsize=12, ha='center')
ax.text(S[0] - 0.2, S[1] - 0.2, 'S', fontsize=12, ha='right')
ax.text(Q[0] + 0.2, Q[1] + 0.2, 'Q', fontsize=12, va='bottom')

# Add side labels
# Position labels slightly away from the sides
ax.text((O[0] + S[0])/2, (O[1] + S[1])/2 - 0.2, f's ({s_length})', fontsize=12, ha='center', va='top')
ax.text((O[0] + Q[0])/2 - 0.2, (O[1] + Q[1])/2, f'q ({q_length})', fontsize=12, ha='right', va='center')
# Position label p roughly in the middle of the hypotenuse
ax.text((S[0] + Q[0])/2 + 0.2, (S[1] + Q[1])/2, f'p ({p_length:.2f})', fontsize=12, ha='left', va='bottom', rotation=np.degrees(np.arctan2(Q[1] - S[1], Q[0] - S[0])))


# Add right angle indicator at O
# Smaller square near the corner O
ax.plot([O[0], O[0] + 0.2, O[0] + 0.2, O[0]], [O[1] + 0.2, O[1] + 0.2, O[1], O[1]], 'k-')


# Set plot limits and aspect ratio
ax.set_xlim(S[0] - 1, Q[0] + 1)
ax.set_ylim(O[1] - 1, Q[1] + 1)
ax.set_aspect('equal', adjustable='box')

# Hide axes
ax.axis('off')

# Show the plot
plt.title('Right Triangle SOQ')
plt.show()