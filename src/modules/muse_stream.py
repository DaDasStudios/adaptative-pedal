from pylsl import StreamInlet, resolve_streams, StreamInfo
from modules.constants import LSL_EEG_CHUNK, SUBSAMPLE
import numpy as np


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
        self.times = np.arange(-self.window, 0, 1.0 / self.sfreq)
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
            "%s - %.1f" % (self.ch_names[ii], self.impedances[ii])
            for ii in range(self.n_chan)
        ]

        self.bf, self.af, self.filt_state, self.data_f = None, None, None, None

        ax.set_yticklabels(ticks_labels)
        ax.set_xlabel("Time (s)")
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
