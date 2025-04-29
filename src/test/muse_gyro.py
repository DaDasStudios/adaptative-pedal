from pylsl import StreamInlet, resolve_streams, StreamInfo
import muselsl
from time import sleep, time
import numpy as np
import matplotlib.pyplot as plt
from threading import Thread
import sys
from scipy.signal import lfilter, lfilter_zi, firwin

# ---------- CONFIG ----------
SUBSAMPLE = 2
LSL_EEG_CHUNK = 12
# ----------------------------

class MuseStream:
    def __init__(self, stream: StreamInfo, filter: bool, scale: int, window: int):  
        self.stream = stream
        self.inlet = StreamInlet(stream, max_chunklen=LSL_EEG_CHUNK)
        self.info = self.inlet.info()
        description = self.info.desc()
        self.type = stream.type()
        self.sfreq = self.info.nominal_srate()
        self.n_samples = int(self.sfreq * window)
        self.n_chan = self.info.channel_count()
        self.filt = filter
        self.subsample = SUBSAMPLE
        self.scale = scale
        self.window = window

        # * Find the channel names
        ch = description.child("channels").first_child()
        self.ch_names = [ch.child_value("label")]
        for i in range(self.n_chan):
            ch = ch.next_sibling()
            self.ch_names.append(ch.child_value("label"))

    def setup_ax(self, ax):
        # * Set the initial data with only zeros and the channels of information
        self.data = np.zeros((self.n_samples, self.n_chan))
        self.times = np.arange(-self.window, 0, 1. / self.sfreq)
        self.axes = ax
        self.lines = []
        for ii in range(self.n_chan):
            (line,) = self.axes.plot(
                self.times[::SUBSAMPLE], self.data[::SUBSAMPLE, ii] - ii, lw=1
            )
            self.lines.append(line)
        self.axes.set_ylim(-self.n_chan + 0.5, 0.5)
        ticks = np.arange(0, -self.n_chan, -1)
        self.impedances = np.std(self.data, axis=0)
        ticks_labels = [
            "%s - %.1f" % (self.ch_names[ii], self.impedances[ii]) for ii in range(self.n_chan)
        ]

        self.bf, self.af, self.filt_state, self.data_f = None, None, None, None

        ax.set_yticklabels(ticks_labels)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel(self.type)
        ax.xaxis.grid(False)
        ax.set_yticks(ticks)

    def __str__(self):
        message = f"""Stream info [{self.type}]:
        Nominal frecuency: {self.sfreq} Hz
        Number of samples: {self.n_samples}
        Number of channels: {self.n_chan}
        Channels: {self.ch_names}
        """
        return message

class LSLViewer:
    def __init__(self, acc_stream: MuseStream, fig, axes):
        self.fig = fig
        self.fig.canvas.mpl_connect("key_press_event", self.OnKeypress)
        self.fig.canvas.mpl_connect("close_event", self.stop_event)
        self.curr_stream = 0
        # * Set the initial rest data
        self.acc_stream = acc_stream
        self.acc_stream.setup_ax(axes)

        # ? Choose the higher frecunecy
        maxFreq = self.acc_stream.sfreq
        print("Maxima frecuencia", maxFreq)
        self.display_every = int(0.1 / (12 / 255))
        print("Se muestra cada: ", self.display_every*0.2, "s")
        help_str = """
            toogle full screen : f
            zoom out : /
            zoom in : *
            increase time scale : -
            decrease time scale : +
            """
        print(help_str)

    def OnKeypress(self, event):
        if event.key == "/":
            self.acc_stream.scale *= 1.2
        elif event.key == "*":
            self.acc_stream.scale /= 1.2
        elif event.key == "+":
            self.acc_stream.window += 1
        elif event.key == "-":
            if self.acc_stream.window > 1:
                self.acc_stream.window -= 1

    def update_plot(self):
        k = 0
        try:
            while self.started:
                muse_stream = self.acc_stream
                samples, timestamps = self.acc_stream.inlet.pull_chunk(timeout=0.1,max_samples=LSL_EEG_CHUNK)
                if timestamps:
                    timestamps = np.float64(np.arange(len(timestamps)))
                    timestamps /= muse_stream.sfreq
                    timestamps += muse_stream.times[-1] + 1.0 / muse_stream.sfreq

                    # muse_stream.times = np.concatenate(
                    #     [muse_stream.times, timestamps]
                    # )
                    muse_stream.n_samples = int(muse_stream.sfreq * muse_stream.window)
                    muse_stream.times = muse_stream.times[
                        -muse_stream.n_samples :
                    ]

                    muse_stream.data = np.vstack([muse_stream.data, samples])
                    muse_stream.data = muse_stream.data[-muse_stream.n_samples :]

                    if k == self.display_every:
                        media = muse_stream.data.mean(axis=0)
                        plot_data = muse_stream.data - media
                        print(f"Mean: {media}")
                        for ii in range(muse_stream.n_chan):
                            if muse_stream.type == "GYRO":
                                print(f"{muse_stream.ch_names[ii]}:", plot_data[-1, ii], end=" ")
                            muse_stream.lines[ii].set_xdata(
                                muse_stream.times[:: muse_stream.subsample]
                                - muse_stream.times[-1]
                            )
                            muse_stream.lines[ii].set_ydata(
                                plot_data[:: muse_stream.subsample, ii] / muse_stream.scale
                                - ii
                            )
                            impedances = np.std(plot_data, axis=0)
                        print("")
                        ticks_labels = [
                            "%s - %.2f" % (muse_stream.ch_names[ii], impedances[ii])
                            for ii in range(muse_stream.n_chan)
                        ]
                        muse_stream.axes.set_yticklabels(ticks_labels)
                        muse_stream.axes.set_xlim(-muse_stream.window, 0)
                        self.fig.canvas.draw()
                        k = 0
                    else:
                        # sleep(0.2)
                        pass
                    k += 1
            print("End")
        except RuntimeError as e:
            raise 

    def start(self):
        self.started = True
        self.thread = Thread(target=self.update_plot)
        self.thread.daemon = True
        self.thread.start()
        plt.show()

    def stop_event(self, close_event):
        self.started = False
        print("Killing all the threads")
        sys.exit()

def plot_data():
    # * Then search for the data that is being streamed
    print("Buscando stream EEG...")
    streams = resolve_streams()

    if (len(streams) == 0):
        raise (RuntimeError("No streams found"))

    acc_stream: MuseStream = None
    for stream in streams:
        if stream.type() == "GYRO":
            filter = False
            scale = 100
            window = 10
            acc_stream = MuseStream(stream, filter, scale, window)
            print(acc_stream)
            print("")

    # * Creating tbe canvas with all the plots we found in the stream
    figure = "15x6"
    figsize = np.int16(figure.split('x'))
    fig, axes = plt.subplots(1, figsize=figsize)
    lsl_viewer = LSLViewer(acc_stream, fig, axes)
    lsl_viewer.start()

plot_data()
