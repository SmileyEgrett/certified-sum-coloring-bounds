#include <array>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <algorithm>

static constexpr int MAXN = 4096;
struct Enumerator {
    int n{};
    int words{};
    int maxk{};
    std::vector<std::vector<uint64_t>> greater_comp;
    std::vector<unsigned long long> counts;
    std::vector<int> stack;
    std::ofstream sets6;
    unsigned long long id6=0;

    void rec(int depth, const std::vector<uint64_t>& cand) {
        for (int wi=0; wi<words; ++wi) {
            uint64_t bits=cand[wi];
            while(bits) {
                int b=__builtin_ctzll(bits);
                bits &= bits-1;
                int v=wi*64+b;
                if(v>=n) continue;
                stack.push_back(v);
                counts[depth+1]++;
                if(depth+1==6 && sets6.is_open()) {
                    sets6 << (++id6) << "\t6\t";
                    for(size_t i=0;i<stack.size();++i) {
                        if(i) sets6 << ' ';
                        sets6 << stack[i]+1;
                    }
                    sets6 << '\n';
                }
                if(depth+1<maxk) {
                    std::vector<uint64_t> next(words);
                    bool any=false;
                    for(int j=0;j<words;++j) {
                        next[j]=cand[j] & greater_comp[v][j];
                        any |= next[j]!=0;
                    }
                    if(any) rec(depth+1,next);
                }
                stack.pop_back();
            }
        }
    }
};

int main(int argc,char**argv){
    if(argc<2 || argc>4){
        std::cerr << "usage: census_stable_sets GRAPH [MAXK=7] [SETS6_OUT]\n";
        return 2;
    }
    std::string graph=argv[1];
    int maxk=argc>=3?std::stoi(argv[2]):7;
    std::ifstream in(graph);
    if(!in) throw std::runtime_error("cannot open graph");
    int n=-1; long long declared=-1; long long seen=0;
    std::vector<std::pair<int,int>> edges;
    std::string line;
    while(std::getline(in,line)){
        if(line.empty()) continue;
        std::istringstream ss(line);
        std::string tag; ss>>tag;
        if(!ss) continue;
        if(tag=="c") continue;
        if(tag=="p"){
            std::string kind; ss>>kind>>n>>declared;
            if(n<=0 || n>MAXN) throw std::runtime_error("bad header");
        } else if(tag=="e"){
            int u,v; ss>>u>>v;
            if(n<0 || u<1 || u>n || v<1 || v>n || u==v) throw std::runtime_error("bad edge");
            --u;--v; if(u>v) std::swap(u,v);
            edges.emplace_back(u,v); seen++;
        } else {
            // DIMACS comments can have leading spaces; anything else is invalid.
            throw std::runtime_error("unexpected record: "+tag);
        }
    }
    if(n<0 || seen!=declared) throw std::runtime_error("edge count mismatch");
    std::sort(edges.begin(),edges.end());
    if(std::adjacent_find(edges.begin(),edges.end())!=edges.end()) throw std::runtime_error("duplicate edge");
    int words=(n+63)/64;
    std::vector<std::vector<uint64_t>> graph_adj(n,std::vector<uint64_t>(words));
    for(auto [u,v]:edges){ graph_adj[u][v/64] |= 1ULL<<(v%64); graph_adj[v][u/64] |= 1ULL<<(u%64); }
    Enumerator e; e.n=n; e.words=words; e.maxk=maxk; e.counts.assign(maxk+1,0); e.greater_comp.assign(n,std::vector<uint64_t>(words));
    for(int v=0;v<n;++v){
        for(int u=v+1;u<n;++u){
            if(((graph_adj[v][u/64]>>(u%64))&1ULL)==0) e.greater_comp[v][u/64] |= 1ULL<<(u%64);
        }
    }
    if(argc>=4){ e.sets6.open(argv[3]); if(!e.sets6) throw std::runtime_error("cannot open sets output"); e.sets6 << "id\tsize\tvertices\n"; }
    std::vector<uint64_t> all(words,~0ULL);
    if(n%64) all.back()=(1ULL<<(n%64))-1;
    e.rec(0,all);
    std::cout << "vertices=" << n << "\n";
    std::cout << "edges=" << declared << "\n";
    for(int k=1;k<=maxk;++k) std::cout << "stable_sets_size_" << k << "=" << e.counts[k] << "\n";
    return 0;
}
