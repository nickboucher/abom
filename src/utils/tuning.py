#!/usr/bin/env python3
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib import colormaps
import numpy as np
from abom import CompressedBloomFilter
from hashlib import sha3_256
from json import dump, load
from tqdm.auto import tqdm
from warnings import catch_warnings, simplefilter
from argparse import ArgumentParser, Namespace
from collections import defaultdict
from os import makedirs
from os.path import join
from matplotlib.collections import PolyCollection
from math import log


class BFStats():
    def __init__(self, bf=None, n=None, json=None):
        # m: Number of bits in Bloom filter
        self.m = bf.m if bf else json['m']
        # k: Number of hash functions
        self.k = bf.k if bf else json['k']
        # n: Number of elements inserted
        self.n = n if bf else json['n']
        # fpr: Experimentally estimated false positive rate
        self.fpr = ~bf if bf else json['fpr']
        # p: Theoretical p value from Mitzenmacher paper
        self.p = ((1 - 1/self.m) ** (self.k * self.n)) if bf else json['p']
        # f: Exact theoretical false positive rate
        self.f = (1 - self.p) ** self.k if bf else json['f']
        # ones: Number of ones in Bloom filter
        self.ones = bf.A.count() if bf else json['ones']
        # s_bytes: Exeprimental length of Bloom filter in bytes when compressed
        self.s_bytes = len(bf.serialize()) if bf else json['s_bytes']
        # s_bits: Experimental length of Bloom filter in bits when compressed
        self.s_bits = self.s_bytes * 8 if bf else json['s_bits']
        # h: Theoretical entropy value
        self.h = (0 if n == 0 else -self.p * log(self.p, 2) - (1 - self.p) * log(1 - self.p, 2)) if bf else json['h']
        # z_bits: Theoretical ideal compressed size (bits)
        self.z_bits = self.h * self.m if bf else json['z_bits']
        # z_bytes: Theoretical ideal compressed size (bytes)
        self.z_bytes = self.z_bits / 8 if bf else json['z_bytes']


    
    def toJSON(self):
        return {
            'm': self.m,
            'k': self.k,
            'n': self.n,
            'fpr': self.fpr,
            'p': self.p,
            'f': self.f,
            'ones': self.ones,
            's_bytes': self.s_bytes,
            's_bits': self.s_bits,
            'h': self.h,
            'z_bits': self.z_bits,
            'z_bytes': self.z_bytes
        }
    
    @classmethod
    def fromJSON(cls, json):
        return cls(json=json)


def mk_groups(data):
    try:
        newdata = data.items()
    except:
        return

    thisgroup = []
    groups = []
    for key, value in newdata:
        newgroups = mk_groups(value)
        if newgroups is None:
            thisgroup.append((key, value))
        else:
            thisgroup.append((key, len(newgroups[-1])))
            if groups:
                groups = [g + n for n, g in zip(newgroups, groups)]
            else:
                groups = newgroups
    return [thisgroup] + groups

def add_line(ax, xpos, ypos):
    line = plt.Line2D([xpos, xpos], [ypos + .1, ypos],
                      transform=ax.transAxes, color='black')
    line.set_clip_on(False)
    ax.add_line(line)

def label_group_bar(ax, data, colormap='inferno'):
    groups = mk_groups(data)
    xy = groups.pop()
    x, y = zip(*xy)
    ly = len(y)
    xticks = range(1, ly + 1)

    bars = ax.bar(xticks, y, align='center')
    ax.set_xticks(xticks)
    ax.set_xticklabels(x, rotation = 45, size=8)
    ax.set_xlim(.5, ly + .5)
    ax.yaxis.grid(True)

    colors = colormaps[colormap]
    n = 0
    j = 0
    for _, span in groups[0]:
        color = colors(j / len(groups[0]))
        for i in range(n, n + span):
            bars[i].set_color(color)
        n += span
        j += 1

    scale = 1. / ly
    for pos in range(ly + 1):
        add_line(ax, pos * scale, -.1)
    ypos = -.25
    while groups:
        group = groups.pop()
        pos = 0
        for label, rpos in group:
            lxpos = (pos + .5 * rpos) * scale
            ax.text(lxpos, ypos, label, ha='center', transform=ax.transAxes)
            add_line(ax, pos * scale, ypos+.05)
            pos += rpos
        add_line(ax, pos * scale, ypos+.05)
        ypos -= .1

def f_max(f: float) -> str:
    if f == 2**-14:
        return '2^{-14}'
    else:
        return f'{f:f}'

def main() -> None:
    parser = ArgumentParser(prog='ABOM Tuning', description='Tune ABOM parameters via experiments.')
    subparsers = parser.add_subparsers(help='Command to run.', dest='command')

    parser_experiment = subparsers.add_parser('experiment', help='Run tuning experiment.')
    parser_experiment.add_argument('-n', '--max-n', type=int, default=10000, help='Maximum number of elements to insert.')
    parser_experiment.add_argument('-m', '--max-m', type=int, default=24, help='Maximum number of bits in Bloom filter (as Log_2 of bits).')
    parser_experiment.add_argument('-k', '--max-k', type=int, default=6, help='Maximum number of hash functions.')
    parser_experiment.add_argument('-o', '--out', type=str, default='tuning.json', help='Output JSON file.')

    parser_graph = subparsers.add_parser('graph', help='Graph tuning experimental results.')
    parser_graph.add_argument('-f', '--max-f', type=float, default=2**-14, help='Maximum false positive rate to graph.')
    parser_graph.add_argument('-n', '--min-n', type=int, default=1000, help='Minimum number of items inserted for target false positive rate.')
    parser_graph.add_argument('-t', '--top', type=int, default=5, help='Number of optimal Bloom filter configurations to output in table.')
    parser_graph.add_argument('-i', '--input', type=str, default='tuning.json', help='Input JSON file.')
    parser_graph.add_argument('-d', '--out-dir', type=str, default='graphs', help='Directory to hold output graphs.')
    parser_graph.add_argument('-m', '--include-2m', nargs='*', type=int, default=[14, 16, 20, 24], help='The values of 2^m to include on the combined 4D plots.')

    args = parser.parse_args()

    if args.command == 'experiment':
        return experiment(args)
    elif args.command == 'graph':
        return graph(args)
    
    parser.print_help()

def experiment(args: Namespace) -> None:
    stats = []
    hashes = [sha3_256(bytes(i)).hexdigest() for i in range(args.max_n)]

    with catch_warnings():
        simplefilter("ignore")
        for m in tqdm([ 2 ** m_2 for m_2 in range(1,args.max_m+1)], desc='m', leave=True):
            for k in tqdm(range(1, args.max_k+1), desc='k', leave=False):
                bf = CompressedBloomFilter(m, k, prehashed=True)
                for n in tqdm(range(args.max_n+1), desc='n', leave=False):
                    bf += hashes[n-1]
                    stat = BFStats(bf, n)
                    stats.append(stat)
                    if stat.f == 1:
                        break
            with open(args.out, 'w') as f:
                json = list(map(lambda x: x.toJSON(), stats))
                dump(json, f)

def graph(args: Namespace) -> None:
    with open(args.input, 'r') as f:
        stats = list(map(lambda x: BFStats.fromJSON(x), load(f)))

    makedirs(args.out_dir, exist_ok=True)
    graph_4D(stats, args.out_dir, args.max_f)
    optimals = graph_optimals(stats, args.out_dir, args.max_f, args.min_n)
    optimals_table(optimals, args.out_dir, args.max_f, args.min_n, args.top)
    graph_combined_4D(stats, args.out_dir, args.max_f, args.include_2m)

def graph_4D(stats: list[BFStats], out_dir: str, max_f: float, fig: None|Figure = None) -> None:
    if not fig:
        makedirs(join(out_dir, '4D'), exist_ok=True)
    M = defaultdict(list)
    for x in stats:
        M[x.m].append(x)

    for i, (m, X) in enumerate(M.items()):
        if not fig:
            filename = join(out_dir, f'4D/m-{int(log(m, 2))}.pdf')
            print(f'Generating {filename}...')

        F = dict()
        K = defaultdict(list)
        for x in sorted(X, key=lambda x: x.k):
            K[x.k].append(x)
            k_max = x.k
            if x.k not in F:
                F[x.k] = x
            elif x.f <= max_f and F[x.k].n < x.n:
                F[x.k] = x
        
        n_max = max(map(lambda x: x.n, X))
        z_bytes_max = max(map(lambda x: x.z_bytes, X))

        def polygon_under_graph(k):
            N = sorted(k, key=lambda x: x.n)
            return [(N[0].n, 0.)] + [(n.n, n.z_bytes) for n in N] + [(n_max, N[-1].z_bytes), (n_max, 0.)]
        
        if fig:
            ax = fig.add_subplot(1, len(M.keys()), i+1, projection='3d', computed_zorder=False)
        else:
            ax = plt.figure().add_subplot(projection='3d', computed_zorder=False)
        verts = [polygon_under_graph(k) for k in K.values()]
        zs = list(K.keys())

        facecolors = plt.colormaps['viridis_r'](np.linspace(0, 1, len(verts)))
        poly = PolyCollection(verts, facecolors=facecolors, alpha=.7)
        ax.add_collection3d(poly, zs=zs, zdir='y')

        for f in F.values():
            ax.scatter(f.n, f.k, f.z_bytes, c='darkorange', edgecolors='black', linewidths=.25, s=6, zorder=1, label='False Positive\nRate = $' + f_max(max_f).lstrip('0').rstrip('0') + '$')

        ax.set(xlim=(0, n_max), ylim=(1, k_max), zlim=(0, z_bytes_max),
               xlabel='n\nElements Inserted', ylabel='k\nHash Functions', zlabel='z\nCompressed Size\n(bytes)')
        
        ax.xaxis.labelpad = 10
        ax.yaxis.labelpad = 10
        ax.zaxis.labelpad = 15

        handles, labels = plt.gca().get_legend_handles_labels()
        dedup = dict(zip(labels, handles))
        if fig:
            plt.xticks(rotation=15)
            ax.legend(dedup.values(), map(lambda x: x.replace('\n', ' '), dedup.keys()), loc='upper center', fontsize="7")
        else:
            ax.legend(dedup.values(), dedup.keys(), fontsize="9")

        ax.set_title(f'$2^{{{log(m, 2):.0f}}}$\nBloom Filter Bits (m)')
        if not fig:
            plt.savefig(filename)
            plt.close()

def graph_combined_4D(stats: list[BFStats], out_dir: str, max_f: float, include_2m: list[int]) -> None:
    stats2 = []
    include_2m = list(map(lambda x: 2**x, include_2m))
    for stat in stats:
        if stat.m in include_2m:
            stats2.append(stat)
    fig = plt.figure(figsize=plt.figaspect(1/len(include_2m)))
    graph_4D(stats2, out_dir, max_f, fig)
    plt.suptitle('$m,n,k,z$ Relationship\nfor Selected Values', fontsize=16, y=1.05)
    plt.subplots_adjust(wspace=.6)
    plt.savefig(join(out_dir, 'combined_4D.pdf'), bbox_inches='tight', pad_inches=0.55)
    plt.close() 

def graph_optimals(stats: list[BFStats], out_dir: str, max_f: float, min_n: int) -> defaultdict[defaultdict[float]]:
    M = defaultdict(lambda: defaultdict(list))
    for x in stats:
        M[x.m][x.k].append(x)
    optimals = defaultdict(lambda: defaultdict(float))
    for m, K in M.items():
        for k, X in K.items():
            optimal = None
            for x in sorted(X, key=lambda x: x.n):
                if x.f <= max_f:
                    optimal = x
                else:
                    if optimal.z_bytes > 0 and optimal.n >= min_n:
                        optimals[f'$2^{{{log(m,2):.0f}}}$'][f'({optimal.n},{optimal.k})'] = round(optimal.z_bytes)
                    break

    fig = plt.figure()
    fig.set_figwidth(15)
    ax = fig.add_subplot(1,1,1)
    label_group_bar(ax, optimals)
    fig.subplots_adjust(bottom=0.3)
    plt.title(f'$m,n,k$\nfor $f\leq{f_max(max_f).lstrip("0")}$ and $n\geq{min_n}$', fontsize=16, y=1.05)
    plt.ylabel('Compressed Size (bytes)\n$z$')
    plt.xlabel('$m, (n,k)$\nBloom Filter Bits, (Elements, Hash Functions)', labelpad=25)
    fig.savefig(join(out_dir,'optimals.pdf'), bbox_inches='tight')
    plt.close()
    return optimals

def optimals_table(optimals: defaultdict[defaultdict[float]], out_dir: str, max_f: float, min_n: int, t: int) -> None:
    rows = []
    for m, NK in optimals.items():
        for nk, z in NK.items():
            n, k = nk.strip('()').split(',')
            c = f'{z/int(n):.3f}'
            rows.append([z, m, n, k, c])
    rows.sort(key=lambda x: x[0])

    fig, ax = plt.subplots()
    fig.set_figheight(t/5)
    ax.axis('off')
    ax.table(cellText=rows[:t], colLabels=('z', 'm', 'n', 'k', 'bytes per item'), loc='center')
    plt.title(f'Top {t} Optimal $(m,n,k,z)$\nfor $f\leq{f_max(max_f).lstrip("0")}$ and $n\geq{min_n}$', pad=20)
    fig.savefig(join(out_dir,'optimals_table.pdf'), bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    main()