import os
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import MaxNLocator
import matplotlib.animation as animation
import matplotlib.cm as cm

def plot_matrix(matrix_list,title_list,fig_title='', global_max=1, save_dir='outputs/'):
    assert(len(matrix_list)==len(title_list)), f"Expected matrix_list and title_list to have the same length. Got lists of length {len(matrix_list)} and {len(title_list)}."
    n = len(matrix_list)
    if n == 1:
        width, height = 6.5, 8
    else:
        width = min(6 * n + 0.5, 15)
        height = 8
    
    fig, ax = plt.subplots(1, n, figsize=(width, height), layout="tight")
    if n == 1:
         ax = [ax]
    

    global_max = np.max([np.max(np.abs(E)) for E in matrix_list if E is not None]) if global_max is None else global_max
    for idx,(E,title) in enumerate(zip(matrix_list,title_list)):  
        im = ax[idx].imshow(E,cmap='bwr',vmin=-global_max,vmax=global_max,aspect='auto')
        ax[idx].set_title(title)

        fig.colorbar(im, ax=ax[idx], fraction=0.046, pad=0.04)
    
    fig.suptitle(fig_title,fontsize=16,fontweight='bold')
    clean_title = fig_title.strip().replace(" ", "_") if fig_title else "matrix_plot"
    filename = os.path.join(save_dir, f"{clean_title}.png")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close(fig)

def animate_matrices(matrix_list:list[np.ndarray], xlabel:str = '', ylabel:str = '', fig_title: str = '', subsample=10, fps=15, save_dir='outputs/',cmap='Blues'):
    """
    Creates a time-lapse animation of matrix values.
    
    Args:
        matrix_list: List of 2D matrices to display
        subsample: How many epochs to skip between frames to speed up the video
        fps: Frames per second for the playback
    """
    matrix_list = matrix_list[::subsample]
    n_frames = len(matrix_list)
    n_rows, n_cols = matrix_list[0].shape
    
    fig, ax = plt.subplots(figsize=(6, 8))
    
    cax = ax.imshow(matrix_list[0], aspect='auto', cmap=cmap, 
                    vmin=0, vmax=1, interpolation='nearest')
    
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    title_object = ax.set_title(fig_title + ' - Epoch: 1')
    fig.colorbar(cax, ax=ax, label='Value')
    
    ax.set_xticks(np.arange(n_cols))
    #ax.set_xticklabels([f'Cluster {i}' for i in range(n_high)])
    
    # The update function called for each frame
    def update(frame):
        # Update the data in the heatmap
        cax.set_array(matrix_list[frame])
        # Update the title with the correct epoch number
        title_object.set_text(fig_title + f" - Epoch: {frame * subsample + 1}")
        return cax, title_object

    # Build the animation
    ani = animation.FuncAnimation(fig, update, frames=n_frames, 
                                  interval=1000/fps, blit=False)
    
    # Close the static figure so it doesn't print twice in Jupyter
    plt.close(fig)
    clean_title = fig_title.strip().replace(" ", "_") if fig_title else "training_curve"
    filename = os.path.join(save_dir, f"{clean_title}.png")
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    ani.save(filename, writer='pillow', fps=15)

def plot_loss_history(history: dict, primary_losses, secondary_losses = [],step: int = 10, log_scale: bool = False, fig_title='Training Curve', figsize: tuple = (12, 5), save_dir='outputs/'):
    """
    Plots all loss trajectories from a training history dictionary.

    Parameters:
        history: Dictionary where keys are loss names and values are lists of loss values per epoch.
        step: Subsampling step size for epochs (default: 10).
        log_scale: Whether to set y-axis to log scale for the primary losses (default: True).
        figsize: Figure dimensions (width, height).

    Returns:
        fig, axes: Matplotlib figure and array of axes.
    """
    # Separate keys into primary losses and secondary/regularizer losses if present
    primary_losses = [k for k in primary_losses if k in history]
    secondary_losses = [k for k in secondary_losses if k in history]

    # Determine subplots needed
    num_plots = (1 if primary_losses else 0) + (1 if secondary_losses else 0)
    if num_plots == 0:
        raise ValueError("History dictionary contains no recognizable loss keys.")

    fig, axes = plt.subplots(1, num_plots, figsize=figsize, layout="tight")
    if num_plots == 1:
        axes = [axes]

    # Plot primary losses
    if primary_losses:
        ax = axes[0]
        for key in primary_losses:
            data = history[key]
            epochs = range(0, len(data), step)
            label = key.replace('_', ' ').title()
            ax.plot(epochs, data[::step], label=label)

        if log_scale:
            ax.set_yscale('log')
        ax.set_xlabel("Epoch")
        #ax.set_ylabel("Loss")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)

    # Plot secondary losses
    if secondary_losses:
        ax = axes[1] if len(axes) > 1 else axes[0]
        for key in secondary_losses:
            data = history[key]
            epochs = range(0, len(data), step)
            label = key.replace('_', ' ').title()
            ax.plot(epochs, data[::step], label=label)

        ax.set_xlabel("Epoch")
        #ax.set_ylabel("Loss")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)

    fig.suptitle(fig_title,fontsize=16,fontweight='bold')
    clean_title = fig_title.strip().replace(" ", "_") if fig_title else "training_curve"
    filename = os.path.join(save_dir, f"{clean_title}.png")
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close(fig)

def _draw_seat(ax, x, y, seat_idx, guest_name, label_dx, label_dy, ha, va, radius=0.3):
    filled = guest_name is not None
    ax.add_patch(plt.Circle((x, y), radius, facecolor='lightseagreen' if filled else 'whitesmoke',
                             edgecolor='black', zorder=3))
    ax.text(x, y, str(seat_idx), ha='center', va='center', fontsize=7, zorder=4)
    ax.text(x + label_dx, y + label_dy, guest_name if filled else '(empty)',
            ha=ha, va=va, fontsize=9, fontstyle='normal' if filled else 'italic',
            color='black' if filled else 'gray')

def _draw_banquet_table(ax, table, guest_of_seat):
    row_spacing, table_width, seat_radius = 1.2, 2.0, 0.3
    head_seat, foot_seat = bool(table.head_seat), bool(table.foot_seat)
    num_side_seats = table.num_seats - int(head_seat) - int(foot_seat)
    num_rows = num_side_seats // 2
    table_height = num_rows * row_spacing

    ax.add_patch(Rectangle((-table_width / 2, 0), table_width, table_height,
                            linewidth=2, edgecolor='black', facecolor='#f0f0f0', zorder=1))

    if head_seat:
        _draw_seat(ax, 0, table_height + 0.6, 0, guest_of_seat.get(0), 0, 0.4, 'center', 'bottom', seat_radius)

    offset = 1 if head_seat else 0
    for i in range(num_side_seats):
        idx = i + offset
        row = i // 2
        side = 1 if i % 2 == 0 else -1
        x = side * (table_width / 2 + 0.4)
        y = table_height - row * row_spacing - row_spacing / 2
        label_dx = 0.4 if side > 0 else -0.4
        ha = 'left' if side > 0 else 'right'
        _draw_seat(ax, x, y, idx, guest_of_seat.get(idx), label_dx, 0, ha, 'center', seat_radius)

    if foot_seat:
        foot_idx = table.num_seats - 1
        _draw_seat(ax, 0, -0.6, foot_idx, guest_of_seat.get(foot_idx), 0, -0.4, 'center', 'top', seat_radius)

    ax.set_xlim(-6, 6)
    ax.set_ylim(-2, table_height + 2)
    ax.set_aspect('equal')
    ax.axis('off')

def _draw_cabaret_table(ax, table, guest_of_seat):
    table_radius, seat_radius = 1.2, 0.3
    orbit_radius = table_radius + 0.7

    ax.add_patch(plt.Circle((0, 0), table_radius, edgecolor='black', facecolor='#f0f0f0', zorder=1))

    for i in range(table.num_seats):
        angle = np.pi / 2 - 2 * np.pi * i / table.num_seats
        x, y = orbit_radius * np.cos(angle), orbit_radius * np.sin(angle)
        label_dx, label_dy = 0.4 * np.cos(angle), 0.4 * np.sin(angle)
        ha = 'left' if np.cos(angle) > 0.1 else ('right' if np.cos(angle) < -0.1 else 'center')
        va = 'bottom' if np.sin(angle) > 0.1 else ('top' if np.sin(angle) < -0.1 else 'center')
        _draw_seat(ax, x, y, i, guest_of_seat.get(i), label_dx, label_dy, ha, va, seat_radius)

    limit = orbit_radius + 1.2
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.set_aspect('equal')
    ax.axis('off')

def _draw_theatre_section(ax, table, guest_of_seat):
    row_spacing, col_spacing, seat_radius = 1.0, 1.0, 0.3
    num_cols = table.num_seats // table.num_rows

    ax.text((num_cols - 1) * col_spacing / 2, row_spacing * 0.5, 'STAGE',
            ha='center', va='center', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='#d0d0d0', edgecolor='black'))

    for i in range(table.num_seats):
        row, col = divmod(i, num_cols)
        x, y = col * col_spacing, -row * row_spacing - row_spacing
        _draw_seat(ax, x, y, i, guest_of_seat.get(i), 0, -0.4, 'center', 'top', seat_radius)

    ax.set_xlim(-1, num_cols * col_spacing)
    ax.set_ylim(-table.num_rows * row_spacing - 1, row_spacing + 0.5)
    ax.set_aspect('equal')
    ax.axis('off')

_TABLE_DRAWERS = {
    'banquet': _draw_banquet_table,
    'cabaret': _draw_cabaret_table,
    'theatre': _draw_theatre_section,
}

def plot_seating_chart(tables, guest_list, seat_of_guest, fig_title='Seating Chart', save_dir='outputs/'):
    """
    Draws every table with its seats laid out per table type (banquet: zig-zag
    down two sides, cabaret: round, theatre: row/column grid), each seat shown
    as a circle labelled with the seated guest's name.

    tables: list of app.schema Table instances (BanquetTable/CabaretTable/TheatreSection)
    guest_list: list of app.schema Guest instances, indexed the same way as seat_of_guest's keys
    seat_of_guest: {guest_index: global_seat_index}, e.g. from a Hungarian-algorithm
        extraction of a GradSolver's soft assignment. Seats are numbered globally
        across all tables, in table order (matching table_adjacency's block-diagonal layout).
    """
    guest_name_of_seat = {seat: guest_list[guest_idx].name for guest_idx, seat in seat_of_guest.items()}

    n_tables = len(tables)
    n_cols = min(n_tables, 3)
    n_rows = -(-n_tables // n_cols)
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 6 * n_rows))
    axes = np.atleast_1d(axes).flatten()

    seat_offset = 0
    for ax, table in zip(axes, tables):
        table_guest_of_seat = {
            local_idx: guest_name_of_seat.get(seat_offset + local_idx)
            for local_idx in range(table.num_seats)
        }
        drawer = _TABLE_DRAWERS.get(table.type)
        if drawer is None:
            raise ValueError(f"Unknown table type: {table.type}")
        drawer(ax, table, table_guest_of_seat)
        ax.set_title(f"Table {table.id}", fontsize=12)
        seat_offset += table.num_seats

    for ax in axes[n_tables:]:
        ax.axis('off')

    fig.suptitle(fig_title, fontsize=16, fontweight='bold')
    fig.tight_layout()
    clean_title = fig_title.strip().replace(" ", "_") if fig_title else "seating_chart"
    filename = os.path.join(save_dir, f"{clean_title}.png")
    os.makedirs(os.path.dirname(filename), exist_ok=True)

    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close(fig)