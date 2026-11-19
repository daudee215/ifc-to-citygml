// Local CGAL comparison executable. CGAL package licence applies to linked code.
#include <CGAL/Simple_cartesian.h>
#include <CGAL/Quotient.h>
#include <CGAL/MP_Float.h>
#include <CGAL/Surface_mesh.h>
#include <CGAL/Polygon_mesh_processing/corefinement.h>
#include <CGAL/Polygon_mesh_processing/self_intersections.h>
#include <CGAL/Polygon_mesh_processing/orientation.h>
#include <CGAL/boost/graph/helpers.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <vector>
using FT=CGAL::Quotient<CGAL::MP_Float>;
using K=CGAL::Simple_cartesian<FT>;
using Mesh=CGAL::Surface_mesh<K::Point_3>;
namespace PMP=CGAL::Polygon_mesh_processing;
Mesh read(const char* name){
 std::ifstream in(name);std::string magic;size_t nv,nf,ne;in>>magic>>nv>>nf>>ne;
 if(!in||magic!="OFF"||nv>100000||nf>200000)throw std::runtime_error("Invalid or over-budget OFF");
 Mesh mesh;std::vector<Mesh::Vertex_index> vertices;
 for(size_t i=0;i<nv;i++){double x,y,z;in>>x>>y>>z;vertices.push_back(mesh.add_vertex(K::Point_3(FT(x),FT(y),FT(z))));}
 for(size_t i=0;i<nf;i++){size_t n,a,b,c;in>>n>>a>>b>>c;if(n!=3||a>=nv||b>=nv||c>=nv)throw std::runtime_error("Only triangle OFF accepted");if(mesh.add_face(vertices[a],vertices[b],vertices[c])==Mesh::null_face())throw std::runtime_error("Nonmanifold input");}
 if(!in||!CGAL::is_closed(mesh)||PMP::does_self_intersect(mesh)||!PMP::does_bound_a_volume(mesh))throw std::runtime_error("Input not a valid closed volume");
 return mesh;
}
void exact_coordinate(std::ostream& out,const FT& value){
 CGAL::print(out,value.numerator());out<<'\t';CGAL::print(out,value.denominator());out<<'\t';
}
int main(int argc,char** argv){
 try{
  if(argc<4)throw std::runtime_error("Usage: exact_union output.off input1.off input2.off ...");
  Mesh result=read(argv[2]);
  for(int i=3;i<argc;i++){Mesh next=read(argv[i]),out;if(!PMP::corefine_and_compute_union(result,next,out))throw std::runtime_error("Union cannot be represented as a manifold mesh");result=std::move(out);}
  if(!CGAL::is_closed(result)||PMP::does_self_intersect(result))throw std::runtime_error("Invalid exact output");
  std::ofstream out(argv[1]);out<<std::setprecision(17)<<"OFF\n"<<result.number_of_vertices()<<' '<<result.number_of_faces()<<" 0\n";
  std::ofstream rational(std::string(argv[1])+".rational.txt");rational<<std::setprecision(17);
  std::vector<size_t> index(result.num_vertices());size_t j=0;
  for(auto v:result.vertices()){auto p=result.point(v);index[v.idx()]=j++;out<<CGAL::to_double(p.x())<<' '<<CGAL::to_double(p.y())<<' '<<CGAL::to_double(p.z())<<'\n';exact_coordinate(rational,p.x());exact_coordinate(rational,p.y());exact_coordinate(rational,p.z());rational<<'\n';}
  for(auto f:result.faces()){out<<3;for(auto v:CGAL::vertices_around_face(result.halfedge(f),result))out<<' '<<index[v.idx()];out<<'\n';}
  std::cout<<"{\"status\":\"exact_union_completed\",\"vertices\":"<<result.number_of_vertices()<<",\"faces\":"<<result.number_of_faces()<<",\"arithmetic\":\"Quotient<MP_Float>; input binary doubles represented exactly\",\"serialization\":\"17-digit double OFF; exact rational vertex file retained\"}"<<std::endl;return 0;
 }catch(const std::exception& error){std::cerr<<error.what()<<std::endl;return 2;}
}
