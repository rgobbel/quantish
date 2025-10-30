import marimo

__generated_with = "0.16.0"
app = marimo.App(width="medium")

with app.setup(hide_code=True):
    # Initialization code that runs before all other cells
    import marimo as mo
    from marimo import md
    import altair as alt
    import numpy as np
    from numpy import array, r_
    import pandas as pd
    import matplotlib.pyplot as plt
    from cmath import cos, sin, pi, phase, exp
    from math import degrees, radians


@app.cell(hide_code=True)
def _(comp_i):
    w_slide = mo.ui.slider(0, 1, step=0.1, value=1, debounce=True, label=f'$w$')
    theta_slide = mo.ui.slider(0, 360, step=5, value=30, debounce=False, label=rf'${{\theta}}$')
    sign_check = mo.ui.checkbox(label='sign', value=True)
    comp_select = mo.ui.multiselect(comp_i, label='Components to plot:')
    w_slide, theta_slide, sign_check, comp_select
    return comp_select, sign_check, theta_slide, w_slide


@app.cell
def _(comp_select, sign_check, theta_slide, w_slide):
    w = w_slide.value + 0j
    theta = radians(theta_slide.value)
    sign = 1 if sign_check.value else -1
    selected_compoments = comp_select.value
    return selected_compoments, sign, theta, w


@app.cell
def _(measure, sign, theta, w):
    measurement = np.array(measure(w, theta, sign))
    return (measurement,)


@app.cell
def _():
    return


@app.cell
def _(measurement, plot_weights, selected_compoments):
    plot_weights(data=measurement, selections=tuple(selected_compoments))
    return


@app.cell(hide_code=True)
def _():
    def cpair(w, theta):
        "basic weight rotation with trig scaling"
        twist = theta - pi/2
        wplus = w * cos(theta) * exp(1j * theta)
        wminus = w * sin(theta) * exp(1j * twist)
        return wplus, wminus
    md(f"### cpair: {cpair.__doc__}")
    return (cpair,)


@app.cell(hide_code=True)
def _(cpair):
    def measure(weight, theta, sign, split=True):
        """measure1(gate, particle, cross, dests, normalize_weights):
        measure a particle through a gate
        """
        # following figure 4.4 in Good and Real
        twist = theta - pi/2
        c1 = weight
        if sign > 0:
            parallel, perpendicular = cpair(c1, theta)
        else:
            parallel, perpendicular = cpair(c1, twist)
        par_a, par_b = cpair(parallel, -theta)
        perp_a, perp_b = cpair(perpendicular, -theta)
        straight = complex(parallel.real, parallel.imag)
        cross = complex(perpendicular.real, perpendicular.imag)
        return straight, cross, parallel, perpendicular, par_a, par_b, perp_a, perp_b
    mo.md('### measure')
    return (measure,)


@app.cell
def _():
    return


@app.cell(hide_code=True)
def _():
    comp_list = ['straight', 'crossed', 'c2', 'c3', 
                 'c2a', 'c2b', 'c3a', 'c3b']
    comp_i = {comp: i for i, comp in enumerate(comp_list)}
    comp_s = {i: comp for i, comp in enumerate(comp_list)}
    def plot_weights(data, selections):
        if selections is None or not selections:
            return None
        sel_i = r_[selections]
        print(sel_i)
        sel_data = array(data)[sel_i]
        sel_comps = tuple([comp_s[i] for i in selections])
        print(f'{sel_comps=}')
        npoints = len(selections)
        # Create figure and axis
        fig, ax = plt.subplots(figsize=(10, 6))

        for x in range(npoints):
            ax.plot([0,sel_data[x].real], [0,sel_data[x].imag], 
                    label=sel_comps[x], linewidth=4)
        # ax.scatter(x[::10], y2[::10], c='r', label='cos(x)', s=50)

        # Customize the plot
        ax.set_xlabel('parallel')
        ax.set_ylabel('perpendicular')
        ax.set(xlim=(-1,1), ylim=(-1,1))
        ax.set_aspect('equal')
        ax.set_title('Weight Splits')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()

        return ax
    md('### plot_weights')
    return comp_i, plot_weights


@app.cell
def _():
    from vega_datasets import data

    source = data.stocks()

    highlight = alt.selection_point(
        on="pointerover", fields=["symbol"], empty=False
    )
    legend_select = alt.selection_point(on='click', fields=['symbol'], bind='legend', empty=False)

    base = alt.Chart(source).encode(
        x="date:T",
        y="price:Q",
        color="symbol:N"
    )

    points = base.mark_circle().encode(
        opacity=alt.value(0)
    ).add_params(
        highlight, legend_select
    ).properties(
        width=600
    )

    lines = base.mark_line().encode(
        size=alt.when(legend_select).then(alt.value(3)).when(highlight & ~legend_select).then(alt.value(2)).otherwise(alt.value(1))
    )

    points + lines
    return data, source


@app.cell
def _(data):
    data.stocks().shape
    return


@app.cell
def _(source):
    source
    return


@app.cell
def _():
    dat = np.random.rand(3,2)
    return (dat,)


@app.cell(disabled=True)
def _(dat):
    pd1 = pd.DataFrame({'x': dat, 'y': np.zeros(len(dat))}, index=['a', 'b', 'c'])
    return (pd1,)


@app.cell
def _(pd1):
    pd1
    return


@app.cell
def _(pd1):
    chart = alt.Chart(data=pd1).mark_rule().encode(
        x=alt.X('x:N', scale=alt.Scale(domain=[-1,1])), 
        y=alt.Y('y:N', scale=alt.Scale(domain=[-1,1]))).properties(width=300, height=300)
    return (chart,)


@app.cell
def _(dat):
    dat[:,0], dat[:,1]
    return


@app.cell
def _(dat):
    pdat = np.pad(dat,((0,0),(2,0))).reshape(6,2)
    return (pdat,)


@app.cell
def _(pdat):
    def create_line_scatter_plot():
        # Generate sample data
        x = pdat[:,0]
        y1 = pdat[:,1]

        # Create figure and axis
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot multiple lines with different styles
        ax.plot(x, y1, 'b-', label='weight', linewidth=1)
        # ax.scatter(x[::10], y2[::10], c='r', label='cos(x)', s=50)

        # Customize the plot
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set(xlim=(-1,1), ylim=(-1,1))
        ax.set_aspect('equal')
        ax.set_title('Basic Line and Scatter Plot')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend()

        return ax

    create_line_scatter_plot()
    return


@app.cell
def _(chart):
    chart
    return


if __name__ == "__main__":
    app.run()
