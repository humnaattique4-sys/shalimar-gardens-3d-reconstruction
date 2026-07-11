from plyfile import PlyData
import matplotlib.pyplot as plt

path = r"C:\Users\DELL\OneDrive\Desktop\New folder\output\shalimar_gardens_reconstruction.ply"
ply = PlyData.read(path)
vertex = ply['vertex']

x, y, z = vertex['x'], vertex['y'], vertex['z']

fig = plt.figure(figsize=(8,8))
ax = fig.add_subplot(111, projection='3d')
ax.scatter(x, y, z, c='goldenrod', s=40)
ax.set_title("Shalimar Gardens - Sparse Reconstruction (42 points)")
plt.savefig("point_cloud_screenshot.png", dpi=150)
plt.show()